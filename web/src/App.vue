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
const goodRate = computed(() => `${((state.value?.stats?.good_rate || 0) * 100).toFixed(1)}%`)
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
const agent = ref(null)
let agentTimer
const agentCycle = computed(() => agent.value?.last_cycle || null)
const agentRoute = computed(() => agentCycle.value?.route?.selected || '—')
const agentFault = computed(() => agentCycle.value?.fault || '无')
const agentProposal = computed(() => {
  const action = agentCycle.value?.proposed_action
  if (!action) return '无提案'
  return `${action.layer || '?'}:${action.name}`
})
const agentAuthority = computed(() => {
  const gate = agentCycle.value?.authority_decision || {}
  if (gate.execution_authority) return gate.execution_authority
  return gate.note || '—'
})
const agentVerify = computed(() => agentCycle.value?.verify_level || agentCycle.value?.recovery_outcome || '—')
const agentExecDetail = computed(() => {
  const result = agentCycle.value?.control_result
  if (!result) return '无'
  const bits = [
    result.request_id || null,
    result.executed ? 'executed' : 'not-executed',
    result.verify_level || null,
    result.recovery_success === true ? 'ok' : (result.recovery_success === false ? 'fail' : null),
  ].filter(Boolean)
  return bits.join(' / ') || '无'
})
const canArmRecovery = computed(() =>
  ownsControl.value
  && agent.value?.available !== false
  && agent.value?.execution_mode === 'execute_replay'
  && !agent.value?.recovery_armed
)
const canDisarmRecovery = computed(() =>
  ownsControl.value && Boolean(agent.value?.recovery_armed)
)
const healthItems = computed(() => [
  ['服务', true],
  ['相机', state.value?.source?.type === 'video' || state.value?.health?.camera?.opened],
  ['模型', state.value?.inspection?.model_loaded],
  ['串口', state.value?.source?.type === 'video' || state.value?.health?.serial?.connected],
  ['Agent', Boolean(agent.value && agent.value.available !== false)],
  ['4B', Boolean(agent.value?.llm_ready)],
])

async function refreshAgent() {
  try {
    agent.value = await request('/agent/status')
    if (agent.value && agent.value.available === undefined) agent.value.available = true
  } catch (exc) {
    agent.value = { available: false, error: exc.message, monitoring: false, llm_ready: false }
  }
}

async function armRecovery() {
  error.value = ''
  busy.value = true
  try {
    agent.value = await request('/agent/recovery/arm', { method: 'POST', body: '{}' })
    if (agent.value && agent.value.available === undefined) agent.value.available = true
  } catch (exc) {
    error.value = exc.message
  } finally {
    busy.value = false
  }
}

async function disarmRecovery() {
  error.value = ''
  busy.value = true
  try {
    agent.value = await request('/agent/recovery/disarm', { method: 'POST', body: '{}' })
    if (agent.value && agent.value.available === undefined) agent.value.available = true
  } catch (exc) {
    error.value = exc.message
  } finally {
    busy.value = false
  }
}

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

onMounted(() => {
  session().catch((exc) => { error.value = exc.message })
  refreshAgent()
  agentTimer = setInterval(refreshAgent, 2000)
})
onBeforeUnmount(() => {
  clearTimeout(reconnectTimer)
  clearInterval(heartbeatTimer)
  clearInterval(agentTimer)
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
            <strong v-if="result?.observations?.length">{{ rejectReason }}</strong>
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
        <article class="panel important-panel">
          <div class="panel-head"><div><span class="eyebrow">INSPECTION STATUS</span><h2>检测判定</h2></div><b>{{ active ? '检测运行中' : '检测已停止' }}</b></div>
          <div :class="['important-verdict', verdictClass]">
            <span>当前判定</span>
            <strong>{{ result?.verdict || (active ? '检测中' : '等待开始') }}</strong>
          </div>
          <div class="important-values">
            <div><span>命中原因</span><strong class="reason-value">{{ result?.observations?.length ? rejectReason : '—' }}</strong></div>
            <div><span>定位数量</span><strong>{{ result?.observations?.length ?? 0 }}<small> 个</small></strong></div>
          </div>
          <div class="runtime-status"><i :class="{ running: active }"></i><span>{{ state.status }}</span></div>
        </article>

        <article class="panel secondary-panel">
          <div class="panel-head"><div><span class="eyebrow">INFERENCE DETAILS</span><h2>推理明细</h2></div><b>{{ modelVersions }}</b></div>
          <div class="probability-list">
            <div><span>划痕融合概率</span><strong>{{ scratchProbability === null ? '—' : (scratchProbability*100).toFixed(2)+'%' }}</strong><small>阈值 {{ state.settings.scratch_threshold.toFixed(6) }}</small></div>
            <div><span>缺齿/缺口概率</span><strong>{{ missingHoleProbability === null ? '—' : (missingHoleProbability*100).toFixed(2)+'%' }}</strong><small>阈值 {{ state.settings.missing_hole_threshold.toFixed(6) }}</small></div>
          </div>
          <div class="detail-grid">
            <span>总耗时<b>{{ result ? result.elapsed_ms.toFixed(1)+' ms' : '—' }}</b></span>
            <span>定位阶段<b>{{ result ? result.timings.locator_ms.toFixed(1)+' ms' : '—' }}</b></span>
            <span>划痕阶段<b>{{ result ? result.timings.scratch.total_ms.toFixed(1)+' ms' : '—' }}</b></span>
            <span>缺口阶段<b>{{ result ? result.timings.missing_hole.total_ms.toFixed(1)+' ms' : '—' }}</b></span>
          </div>
        </article>

        <article class="panel agent-panel">
          <div class="panel-head">
            <div><span class="eyebrow">EDGEMEDIC AGENT</span><h2>4B 诊断状态</h2></div>
            <b>{{ agent?.monitoring ? '监测中' : '未监测' }}</b>
          </div>
          <div class="agent-grid">
            <div><span>服务</span><strong>{{ agent?.available === false ? '离线' : '在线' }}</strong></div>
            <div><span>4B</span><strong>{{ agent?.llm_ready ? '就绪' : '未就绪' }}</strong></div>
            <div><span>执行模式</span><strong>{{ agent?.execution_mode || '—' }}</strong></div>
            <div><span>恢复武装</span><strong>{{ agent?.recovery_armed ? '是' : '否' }}</strong></div>
            <div><span>故障</span><strong>{{ agentFault }}</strong></div>
            <div><span>路由</span><strong>{{ agentRoute }}</strong></div>
            <div><span>提案</span><strong>{{ agentProposal }}</strong></div>
            <div><span>Authority</span><strong>{{ agentAuthority }}</strong></div>
            <div><span>Verify</span><strong>{{ agentVerify }}</strong></div>
            <div><span>已执行</span><strong>{{ agentCycle?.actually_executed ? '是' : '否' }}</strong></div>
            <div class="agent-wide"><span>Control/Verify</span><strong>{{ agentExecDetail }}</strong></div>
          </div>
          <div class="agent-actions">
            <button class="button" type="button" :disabled="busy || !canArmRecovery" @click="armRecovery">启用恢复授权</button>
            <button class="button ghost" type="button" :disabled="busy || !canDisarmRecovery" @click="disarmRecovery">撤销恢复授权</button>
          </div>
          <p class="agent-note">开始检测仅开启监测；恢复授权需操作员显式启用，且仅当 Agent 以 execute_replay 运行（隔离 Replay）。停止检测会撤销授权并停止监测。</p>
        </article>

        <article class="panel stats-panel">
          <div class="panel-head"><div><span class="eyebrow">QUALITY OVERVIEW</span><h2>检测统计</h2></div></div>
          <div class="stats-summary">
            <div><span>已检测</span><strong>{{ state.stats.total }}</strong></div>
            <div class="good"><span>合格</span><strong>{{ state.stats.good }}</strong></div>
            <div class="bad"><span>不合格</span><strong>{{ state.stats.defective }}</strong></div>
          </div>
          <div class="stats-visual">
            <div class="donut" :style="{ '--rate': state.stats.good_rate * 360 + 'deg' }"><span>{{ goodRate }}<small>合格率</small></span></div>
            <div class="legend"><span><i class="good"></i>合格 {{ state.stats.good }}</span><span><i class="bad"></i>不合格 {{ state.stats.defective }}</span></div>
          </div>
        </article>
      </aside>
    </section>

    <footer><span>操作权限：{{ ownsControl ? '当前终端' : (state.control.owner_label || '无人控制') }}</span><span>推理档位：{{ state.settings.inference_profile }}</span><span>划痕阈值：{{ state.settings.scratch_threshold.toFixed(6) }}</span><span>缺口阈值：{{ state.settings.missing_hole_threshold.toFixed(6) }}</span></footer>
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
