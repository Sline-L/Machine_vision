<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

const API = '/api/v2'
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
const goodRateValue = computed(() => Math.max(0, Math.min(100, (state.value?.stats?.good_rate || 0) * 100)))
const defectiveRateValue = computed(() => {
  const stats = state.value?.stats
  return stats?.total ? Math.max(0, Math.min(100, (stats.defective / stats.total) * 100)) : 0
})
const goodRate = computed(() => `${goodRateValue.value.toFixed(1)}%`)
const specialistMaximum = (name, field = 'probability') => {
  const values = result.value?.observations?.map(item => item.specialists?.[name]?.[field]).filter(Number.isFinite) || []
  return values.length ? Math.max(...values) : null
}
const scratchProbability = computed(() => specialistMaximum('scratch'))
const missingHoleProbability = computed(() => specialistMaximum('missing_hole'))
const rejectReason = computed(() => {
  const labels = { scratch: '划痕', missing_hole: '缺齿/缺口' }
  return result.value?.reject_reasons?.map(reason => labels[reason] || reason).join(' + ') || '未命中缺陷'
})
const modelVersions = computed(() => {
  const versions = result.value?.model_versions
  return versions ? `${versions.scratch} + ${versions.missing_hole}` : '模型待加载'
})
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

function resetThresholds() {
  const defaults = state.value?.settings?.model_default_thresholds
  if (!defaults) return
  settings.scratch_threshold = defaults.scratch
  settings.missing_hole_threshold = defaults.missing_hole
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
        <button class="button quiet" :disabled="!ownsControl" @click="openSettings">设置</button>
        <button class="button quiet" @click="logout">退出</button>
      </div>
    </header>

    <div v-if="error || state.error" class="alert"><strong>运行提示</strong>{{ error || state.error }}</div>

    <section class="workspace">
      <article class="panel vision-panel">
        <div class="panel-head">
          <div class="panel-title"><h2>实时检测画面</h2><span>{{ state.source.type === 'video' ? `测试视频 · ${state.source.video_name}` : `相机 ${state.settings.camera_index}` }}</span></div>
          <div class="segmented" aria-label="画面显示模式">
            <button v-for="view in [['auto','自动'],['raw','原图'],['annotated','结果']]" :key="view[0]"
              type="button" :aria-pressed="streamView === view[0]" :class="{ active: streamView === view[0] }" @click="streamView = view[0]">{{ view[1] }}</button>
          </div>
        </div>
        <div class="video-stage">
          <img :key="streamNonce" :src="streamUrl" alt="GearPro 实时检测画面" />
          <div class="frame-status"><i :class="{ running: active }"></i>{{ active ? '检测运行中' : '检测已停止' }}</div>
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
        <article class="panel important-panel">
          <div class="section-heading"><h2>当前检测结果</h2><span>实时判定</span></div>
          <div :class="['important-verdict', verdictClass]" aria-live="polite">
            <span>当前判定</span>
            <div class="verdict-reading">
              <svg v-if="verdictClass === 'good'" viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.2 4.2L19 7" /></svg>
              <svg v-else-if="verdictClass === 'bad'" viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17" /></svg>
              <svg v-else viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="6" /></svg>
              <strong>{{ result?.verdict || (active ? '检测中' : '等待开始') }}</strong>
            </div>
          </div>
          <div class="important-values">
            <div><span>缺陷类型</span><strong class="reason-value">{{ result?.observations?.length ? rejectReason : '—' }}</strong></div>
            <div><span>缺陷数量</span><strong>{{ result?.observations?.length ?? 0 }}<small> 个</small></strong></div>
          </div>
          <div class="runtime-status"><i :class="{ running: active }"></i><span>{{ state.status }}</span></div>
        </article>

        <article class="panel secondary-panel">
          <div class="section-heading"><h2>推理详情</h2><span>{{ modelVersions }}</span></div>
          <div class="probability-list">
            <div>
              <span>划痕</span><strong>{{ scratchProbability === null ? '—' : (scratchProbability*100).toFixed(2)+'%' }}</strong>
              <svg class="probability-chart" viewBox="0 0 100 5" preserveAspectRatio="none" aria-hidden="true">
                <rect class="chart-track" width="100" height="5" rx="1" />
                <rect class="chart-value" :width="scratchProbability === null ? 0 : Math.min(100, scratchProbability * 100)" height="5" rx="1" />
                <line class="chart-threshold" :x1="state.settings.scratch_threshold * 100" :x2="state.settings.scratch_threshold * 100" y1="0" y2="5" />
              </svg>
              <small>阈值 {{ state.settings.scratch_threshold.toFixed(6) }}</small>
            </div>
            <div>
              <span>缺齿</span><strong>{{ missingHoleProbability === null ? '—' : (missingHoleProbability*100).toFixed(2)+'%' }}</strong>
              <svg class="probability-chart" viewBox="0 0 100 5" preserveAspectRatio="none" aria-hidden="true">
                <rect class="chart-track" width="100" height="5" rx="1" />
                <rect class="chart-value" :width="missingHoleProbability === null ? 0 : Math.min(100, missingHoleProbability * 100)" height="5" rx="1" />
                <line class="chart-threshold" :x1="state.settings.missing_hole_threshold * 100" :x2="state.settings.missing_hole_threshold * 100" y1="0" y2="5" />
              </svg>
              <small>阈值 {{ state.settings.missing_hole_threshold.toFixed(6) }}</small>
            </div>
          </div>
          <div class="detail-grid">
            <span>总耗时<b>{{ result ? result.elapsed_ms.toFixed(1)+' ms' : '—' }}</b></span>
            <span>定位阶段<b>{{ result ? result.timings.locator_ms.toFixed(1)+' ms' : '—' }}</b></span>
            <span>划痕阶段<b>{{ result ? result.timings.scratch.total_ms.toFixed(1)+' ms' : '—' }}</b></span>
            <span>缺口阶段<b>{{ result ? result.timings.missing_hole.total_ms.toFixed(1)+' ms' : '—' }}</b></span>
          </div>
        </article>

        <article class="panel stats-panel">
          <div class="section-heading"><h2>质量概览</h2><span>本次运行</span></div>
          <div class="stats-summary">
            <div><span>已检测</span><strong>{{ state.stats.total }}</strong></div>
            <div class="good"><span>合格</span><strong>{{ state.stats.good }}</strong></div>
            <div class="bad"><span>不合格</span><strong>{{ state.stats.defective }}</strong></div>
          </div>
          <div class="rate-row">
            <div><span>综合合格率</span><strong>{{ goodRate }}</strong></div>
            <svg class="quality-chart" viewBox="0 0 100 7" preserveAspectRatio="none" role="img" :aria-label="`合格率 ${goodRate}，不合格 ${state.stats.defective} 个`">
              <rect class="chart-track" width="100" height="7" rx="1" />
              <rect class="chart-good" :width="goodRateValue" height="7" rx="1" />
              <rect class="chart-bad" :x="goodRateValue" :width="defectiveRateValue" height="7" rx="1" />
            </svg>
          </div>
        </article>
      </aside>
    </section>

    <footer><span>操作权限：{{ ownsControl ? '当前终端' : (state.control.owner_label || '无人控制') }}</span><span>推理档位：{{ state.settings.inference_profile }}</span><span>划痕阈值：{{ state.settings.scratch_threshold.toFixed(6) }}</span><span>缺口阈值：{{ state.settings.missing_hole_threshold.toFixed(6) }}</span></footer>
  </main>

  <main v-else class="login-page">
    <form class="login-card" @submit.prevent="login">
      <div class="brand-mark large">GP</div><h1>欢迎回来</h1><p>登录 GearPro 齿轮视觉检测控制台</p>
      <label>终端名称<input v-model="label" required maxlength="64" /></label>
      <label v-if="passwordRequired">访问密码<input v-model="password" type="password" required autofocus /></label>
      <div v-if="error" class="form-error">{{ error }}</div>
      <button class="button primary large" :disabled="busy">{{ busy ? '正在连接…' : '进入控制台' }}</button>
    </form>
  </main>

  <div v-if="settingsOpen" class="modal" @click.self="settingsOpen = false">
    <form class="settings-card" @submit.prevent="saveSettings">
      <div class="settings-title"><div><h2>运行设置</h2><p>调整检测流程、阈值与设备参数</p></div><button type="button" class="button quiet" @click="settingsOpen = false">关闭</button></div>
      <div class="form-grid">
        <label>运行模式<select v-model="settings.mode"><option>自由模式</option><option>定量模式</option><option>定时模式</option><option v-if="settings.mode === '视频测试模式'">视频测试模式</option></select></label>
        <label>推理档位<select v-model="settings.inference_profile"><option>FULL</option><option>SPARSE</option><option>SAFE_STOP</option></select></label>
        <label>目标数量<input v-model.number="settings.target_quantity" type="number" min="1" /></label>
        <label>运行时长（分钟）<input v-model.number="settings.duration_minutes" type="number" min="1" /></label>
        <label>齿轮定位阈值<input v-model.number="settings.locator_confidence" type="number" min="0.01" max="0.99" step="0.01" /></label>
        <label>划痕判定阈值<input v-model.number="settings.scratch_threshold" type="number" min="0.01" max="0.99" step="0.000001" /></label>
        <label>缺齿/缺口阈值<input v-model.number="settings.missing_hole_threshold" type="number" min="0.01" max="0.99" step="0.000001" /></label>
        <label>推理间隔（秒）<input v-model.number="settings.inference_interval" type="number" min="0.03" max="5" step="0.01" /></label>
        <label>摄像头索引<input v-model.number="settings.camera_index" type="number" min="0" max="32" /></label>
        <label>串口设备<input v-model="settings.serial_port" /></label>
        <label>串口波特率<input v-model.number="settings.serial_baudrate" type="number" min="300" /></label>
        <label>画面帧率<input v-model.number="settings.stream_fps" type="number" min="1" max="30" /></label>
        <label>JPEG 质量<input v-model.number="settings.stream_quality" type="number" min="30" max="95" /></label>
      </div>
      <div class="settings-actions"><button type="button" class="button ghost" @click="resetThresholds">恢复模型默认阈值</button><button type="button" class="button" @click="settingsOpen = false">取消</button><button class="button primary" :disabled="busy">保存设置</button></div>
    </form>
  </div>
</template>
