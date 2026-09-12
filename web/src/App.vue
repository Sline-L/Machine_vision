<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

const API = '/api/v1'
const state = ref(null)
const authenticated = ref(false)
const passwordRequired = ref(true)
const password = ref('')
const label = ref(localStorage.getItem('gearpro-terminal') || `终端 ${location.hostname}`)
const error = ref('')
const busy = ref(false)
const settingsOpen = ref(false)
const streamView = ref('auto')
const streamNonce = ref(Date.now())
const uploadInput = ref(null)
const settings = reactive({})
let socket
let reconnectTimer
let heartbeatTimer

const ownsControl = computed(() => state.value?.control?.is_owner === true)
const active = computed(() => state.value?.inspection?.active === true)
const result = computed(() => state.value?.result)
const verdictClass = computed(() => {
  if (!result.value?.has_gear) return 'idle'
  return result.value.is_defective ? 'bad' : 'good'
})
const goodRate = computed(() => `${((state.value?.stats?.good_rate || 0) * 100).toFixed(1)}%`)
const streamUrl = computed(() => `${API}/stream?view=${streamView.value}&v=${streamNonce.value}`)
const healthItems = computed(() => [
  ['服务', true],
  ['相机', state.value?.source?.type === 'video' || state.value?.health?.camera?.opened],
  ['模型', state.value?.inspection?.model_loaded],
  ['串口', state.value?.source?.type === 'video' || state.value?.health?.serial?.connected],
])

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    credentials: 'same-origin',
    headers: options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
    ...options,
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail || `请求失败 (${response.status})`)
  return payload
}

async function session() {
  const info = await request('/session')
  passwordRequired.value = info.password_required
  authenticated.value = info.authenticated
  if (!info.authenticated && !info.password_required) await login()
  else if (info.authenticated) connect()
}

async function login() {
  error.value = ''
  busy.value = true
  try {
    await request('/session/login', {
      method: 'POST',
      body: JSON.stringify({ password: password.value, label: label.value }),
    })
    localStorage.setItem('gearpro-terminal', label.value)
    authenticated.value = true
    password.value = ''
    connect()
  } catch (exc) {
    error.value = exc.message
  } finally {
    busy.value = false
  }
}

async function logout() {
  await request('/session/logout', { method: 'POST' }).catch(() => {})
  authenticated.value = false
  state.value = null
  socket?.close()
}

function connect() {
  clearTimeout(reconnectTimer)
  socket?.close()
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  socket = new WebSocket(`${scheme}://${location.host}${API}/events`)
  socket.onmessage = (event) => {
    state.value = JSON.parse(event.data)
  }
  socket.onclose = (event) => {
    if (event.code === 4401) {
      authenticated.value = false
      return
    }
    if (authenticated.value) reconnectTimer = setTimeout(connect, 1500)
  }
}

async function action(path, body) {
  error.value = ''
  busy.value = true
  try {
    const payload = await request(path, {
      method: body === undefined ? 'POST' : 'PUT',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (payload?.version) state.value = payload
  } catch (exc) {
    error.value = exc.message
  } finally {
    busy.value = false
  }
}

async function acquire() {
  await action('/control/acquire')
}

async function release() {
  await action('/control/release')
}

async function chooseVideo(event) {
  const file = event.target.files?.[0]
  if (!file) return
  error.value = ''
  busy.value = true
  const form = new FormData()
  form.append('file', file)
  try {
    state.value = await request('/source/video', { method: 'POST', body: form })
    streamView.value = 'auto'
    streamNonce.value = Date.now()
  } catch (exc) {
    error.value = exc.message
  } finally {
    event.target.value = ''
    busy.value = false
  }
}

function openSettings() {
  Object.assign(settings, state.value?.settings || {})
  settingsOpen.value = true
}

async function saveSettings() {
  await action('/settings', { ...settings })
  if (!error.value) settingsOpen.value = false
}

watch(ownsControl, (owns) => {
  clearInterval(heartbeatTimer)
  if (owns) {
    heartbeatTimer = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'control_heartbeat' }))
    }, 10000)
  }
})

watch(() => settings.inference_profile, (profile, previous) => {
  if (!settingsOpen.value || profile === previous) return
  if (profile === 'FULL') settings.inference_interval = 0.10
  if (profile === 'SPARSE') settings.inference_interval = 0.20
})

onMounted(() => session().catch((exc) => { error.value = exc.message }))
onBeforeUnmount(() => {
  clearTimeout(reconnectTimer)
  clearInterval(heartbeatTimer)
  socket?.close()
})
</script>

<template>
  <main v-if="authenticated && state" class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">GP</div>
        <div><h1>GearPro</h1><p>齿轮视觉检测系统</p></div>
      </div>
      <div class="health-strip">
        <span v-for="item in healthItems" :key="item[0]" :class="['health-chip', { ok: item[1] }]">
          <i></i>{{ item[0] }}
        </span>
      </div>
      <div class="top-actions">
        <button v-if="!ownsControl" class="button primary" :disabled="busy" @click="acquire">接管控制</button>
        <button v-else class="button subtle" @click="release">释放控制</button>
        <button class="icon-button" title="设置" :disabled="!ownsControl" @click="openSettings">⚙</button>
        <button class="icon-button" title="退出" @click="logout">↪</button>
      </div>
    </header>

    <div v-if="error || state.error" class="alert"><strong>运行提示</strong>{{ error || state.error }}</div>

    <section class="metric-grid">
      <article class="metric"><span>已检测</span><strong>{{ state.stats.total }}</strong><small>件</small></article>
      <article class="metric success"><span>合格</span><strong>{{ state.stats.good }}</strong><small>正常</small></article>
      <article class="metric danger"><span>不合格</span><strong>{{ state.stats.defective }}</strong><small>需复核</small></article>
      <article class="metric rate"><span>合格率</span><strong>{{ goodRate }}</strong><small>本次任务</small></article>
    </section>

    <section class="workspace">
      <article class="panel vision-panel">
        <div class="panel-head">
          <div><span class="eyebrow">LIVE INSPECTION</span><h2>实时检测画面</h2></div>
          <div class="segmented">
            <button v-for="view in [['auto','自动'],['raw','原图'],['annotated','结果']]" :key="view[0]"
              :class="{ active: streamView === view[0] }" @click="streamView = view[0]">{{ view[1] }}</button>
          </div>
        </div>
        <div class="video-stage">
          <img :key="streamNonce" :src="streamUrl" alt="GearPro 实时检测画面" />
          <div :class="['verdict', verdictClass]">
            <span>{{ result?.verdict || (active ? '检测中' : '等待开始') }}</span>
            <strong v-if="result?.observations?.length">{{ (Math.max(...result.observations.map(x => x.defect_score)) * 100).toFixed(1) }}%</strong>
          </div>
          <div class="source-tag">{{ state.source.type === 'video' ? `测试视频 · ${state.source.video_name}` : `CAM ${state.settings.camera_index}` }}</div>
        </div>
        <div class="control-row">
          <button class="button primary large" :disabled="!ownsControl || busy" @click="action(active ? '/inspection/stop' : '/inspection/start')">
            {{ active ? '停止检测' : '开始检测' }}
          </button>
          <input ref="uploadInput" hidden type="file" accept="video/*,.mkv" @change="chooseVideo" />
          <button class="button" :disabled="!ownsControl || busy" @click="uploadInput.click()">上传测试视频</button>
          <button v-if="state.source.type === 'video'" class="button" :disabled="!ownsControl || busy" @click="action('/source/camera')">返回实时相机</button>
          <button class="button ghost" :disabled="!ownsControl || busy" @click="action('/stats/reset')">清空统计</button>
          <span class="status-text"><i :class="{ running: active }"></i>{{ state.status }}</span>
        </div>
      </article>

      <aside class="side-stack">
        <article class="panel result-panel">
          <div class="panel-head"><div><span class="eyebrow">LATEST RESULT</span><h2>最近结果</h2></div><b>{{ result?.model_version || '模型待加载' }}</b></div>
          <div class="probability-list">
            <div><span>融合概率</span><strong>{{ result?.observations?.length ? (Math.max(...result.observations.map(x => x.defect_score))*100).toFixed(2)+'%' : '—' }}</strong></div>
            <div><span>分类器均值</span><strong>{{ result?.observations?.length ? (Math.max(...result.observations.map(x => x.classifier_probability))*100).toFixed(2)+'%' : '—' }}</strong></div>
            <div><span>检测器概率</span><strong>{{ result?.observations?.length ? (Math.max(...result.observations.map(x => x.detector_probability))*100).toFixed(2)+'%' : '—' }}</strong></div>
          </div>
          <div class="detail-grid">
            <span>定位数量<b>{{ result?.observations?.length ?? 0 }}</b></span>
            <span>总耗时<b>{{ result ? result.elapsed_ms.toFixed(1)+' ms' : '—' }}</b></span>
            <span>定位阶段<b>{{ result ? result.locator_latency_ms.toFixed(1)+' ms' : '—' }}</b></span>
            <span>划痕阶段<b>{{ result ? (result.classifier1_latency_ms + result.classifier2_latency_ms + result.detector_latency_ms).toFixed(1)+' ms' : '—' }}</b></span>
          </div>
        </article>

        <article class="panel stats-panel">
          <div class="panel-head"><div><span class="eyebrow">QUALITY OVERVIEW</span><h2>质量统计</h2></div></div>
          <div class="donut" :style="{ '--rate': state.stats.good_rate * 360 + 'deg' }"><span>{{ goodRate }}<small>合格率</small></span></div>
          <div class="legend"><span><i class="good"></i>合格 {{ state.stats.good }}</span><span><i class="bad"></i>不合格 {{ state.stats.defective }}</span></div>
        </article>
      </aside>
    </section>

    <footer><span>操作权限：{{ ownsControl ? '当前终端' : (state.control.owner_label || '无人控制') }}</span><span>推理档位：{{ state.settings.inference_profile }}</span><span>缺陷阈值：{{ state.settings.defect_threshold.toFixed(6) }}</span></footer>
  </main>

  <main v-else class="login-page">
    <form class="login-card" @submit.prevent="login">
      <div class="brand-mark large">GP</div><span class="eyebrow">GEARPRO CONTROL</span><h1>欢迎回来</h1><p>登录齿轮视觉检测控制台</p>
      <label>终端名称<input v-model="label" required maxlength="64" /></label>
      <label v-if="passwordRequired">访问密码<input v-model="password" type="password" required autofocus /></label>
      <div v-if="error" class="form-error">{{ error }}</div>
      <button class="button primary large" :disabled="busy">{{ busy ? '正在连接…' : '进入控制台' }}</button>
    </form>
  </main>

  <div v-if="settingsOpen" class="modal" @click.self="settingsOpen = false">
    <form class="settings-card" @submit.prevent="saveSettings">
      <div class="settings-title"><div><span class="eyebrow">RUNTIME SETTINGS</span><h2>运行设置</h2></div><button type="button" class="icon-button" @click="settingsOpen = false">×</button></div>
      <div class="form-grid">
        <label>运行模式<select v-model="settings.mode"><option>自由模式</option><option>定量模式</option><option>定时模式</option><option v-if="settings.mode === '视频测试模式'">视频测试模式</option></select></label>
        <label>推理档位<select v-model="settings.inference_profile"><option>FULL</option><option>SPARSE</option><option>SAFE_STOP</option></select></label>
        <label>目标数量<input v-model.number="settings.target_quantity" type="number" min="1" /></label>
        <label>运行时长（分钟）<input v-model.number="settings.duration_minutes" type="number" min="1" /></label>
        <label>齿轮定位阈值<input v-model.number="settings.locator_confidence" type="number" min="0.01" max="0.99" step="0.01" /></label>
        <label>缺陷判定阈值<input v-model.number="settings.defect_threshold" type="number" min="0.01" max="0.99" step="0.000001" /></label>
        <label>推理间隔（秒）<input v-model.number="settings.inference_interval" type="number" min="0.03" max="5" step="0.01" /></label>
        <label>摄像头索引<input v-model.number="settings.camera_index" type="number" min="0" max="32" /></label>
        <label>串口设备<input v-model="settings.serial_port" /></label>
        <label>串口波特率<input v-model.number="settings.serial_baudrate" type="number" min="300" /></label>
        <label>画面帧率<input v-model.number="settings.stream_fps" type="number" min="1" max="30" /></label>
        <label>JPEG 质量<input v-model.number="settings.stream_quality" type="number" min="30" max="95" /></label>
      </div>
      <div class="settings-actions"><button type="button" class="button" @click="settingsOpen = false">取消</button><button class="button primary" :disabled="busy">保存设置</button></div>
    </form>
  </div>
</template>
