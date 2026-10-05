<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

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
const connection = ref('connecting')
const sessionLoading = ref(true)
const lastMessageAt = ref(0)
const clock = ref(Date.now())
const pendingFile = ref(null)
const confirmation = ref(null)
const dialog = ref(null)
const streamFailed = ref(false)
const uploading = ref(false)
const awaitingResult = ref(false)
let previousResult = ''
let returnFocus
let freshnessTimer
let socket
let reconnectTimer
let heartbeatTimer

const ownsControl = computed(() => state.value?.control?.is_owner === true)
const active = computed(() => state.value?.inspection?.active === true)
const result = computed(() => awaitingResult.value ? null : state.value?.result)
const connected = computed(() => connection.value === 'connected' && clock.value - lastMessageAt.value < 5000)
const canControl = computed(() => connected.value && ownsControl.value && !busy.value)
const sourceLabel = computed(() => state.value?.source?.type === 'video' ? `测试视频：${state.value.source.video_name}` : `实时相机 ${state.value?.settings?.camera_index ?? ''}`)
const connectionLabel = computed(() => connected.value ? '已连接' : connection.value === 'connected' ? '状态更新超时' : connection.value === 'reconnecting' ? '正在重新连接' : '正在连接设备')
const startBlocked = computed(() => {
  if (!connected.value) return '连接恢复后可操作'
  if (!ownsControl.value) return `请先接管控制；当前控制方：${state.value?.control?.owner_label || '无人控制'}`
  if (active.value) return ''
  if (state.value?.settings?.inference_profile === 'SAFE_STOP') return '请在设置中退出安全停止档位'
  if (state.value?.source?.type !== 'video' && !state.value?.health?.camera?.opened) return '相机未连接，请检查设备'
  return ''
})
const runtimeLabel = computed(() => !connected.value ? connectionLabel.value : state.value?.error ? '检测故障' : active.value ? '检测运行中' : state.value?.status === '当前任务已完成' ? '任务已完成' : '检测已停止')
const verdictLabel = computed(() => result.value?.verdict || (active.value ? '等待检测结果' : '等待开始'))
const historical = computed(() => !connected.value || !active.value)
const formatProbability = value => value === null ? '—' : `${(value * 100).toFixed(2)}%`
const formatMs = value => Number.isFinite(value) ? `${value.toFixed(1)} ms` : '—'
const verdictClass = computed(() => {
  if (historical.value || !result.value?.has_gear) return 'idle'
  return result.value.is_defective ? 'bad' : 'good'
})
const goodRateValue = computed(() => Math.max(0, Math.min(100, (state.value?.stats?.good_rate || 0) * 100)))
const defectShareValue = (name) => {
  const stats = state.value?.stats
  return stats?.defective ? Math.max(0, Math.min(100, ((stats[name] || 0) / stats.defective) * 100)) : 0
}
const goodRate = computed(() => state.value?.stats?.total ? `${goodRateValue.value.toFixed(1)}%` : '—')
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
const healthItems = computed(() => {
  const video = state.value?.source?.type === 'video'
  return [
    ['服务', connected.value ? '已连接' : '失联'],
    ['相机', video ? '未使用' : state.value?.health?.camera?.opened ? '已连接' : '未连接'],
    ['模型', state.value?.inspection?.model_loaded ? '已加载' : '待加载'],
    ['串口', video ? '未使用' : state.value?.health?.serial?.connected ? '已连接' : '未连接'],
  ]
})

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
  clearTimeout(reconnectTimer)
  settingsOpen.value = false
  confirmation.value = null
  pendingFile.value = null
  awaitingResult.value = false
  await request('/session/logout', { method: 'POST' }).catch(() => {})
  authenticated.value = false
  state.value = null
  socket?.close()
}

function connect() {
  clearTimeout(reconnectTimer)
  if (socket) { socket.onclose = null; socket.close() }
  connection.value = state.value ? 'reconnecting' : 'connecting'
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  socket = new WebSocket(`${scheme}://${location.host}${API}/events`)
  socket.onmessage = (event) => {
    try {
      state.value = JSON.parse(event.data)
      if (awaitingResult.value && JSON.stringify(state.value.result) !== previousResult) awaitingResult.value = false
      lastMessageAt.value = Date.now()
      clock.value = Date.now()
      connection.value = 'connected'
    } catch { error.value = '无法读取设备状态，请重新连接' }
  }
  socket.onclose = (event) => {
    connection.value = 'reconnecting'
    if (event.code === 4401) {
      authenticated.value = false
      return
    }
    if (authenticated.value) reconnectTimer = setTimeout(connect, 1500)
  }
}

async function action(path, body) {
  if (!canControl.value && path !== '/control/acquire') return
  if (!connected.value) return
  error.value = ''
  busy.value = true
  if (path === '/inspection/start' || path === '/source/camera') {
    previousResult = JSON.stringify(state.value?.result)
    awaitingResult.value = true
  }
  try {
    const payload = await request(path, {
      method: body === undefined ? 'POST' : 'PUT',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (payload?.version) state.value = payload
  } catch (exc) {
    awaitingResult.value = false
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
  event.target.value = ''
  if (!canControl.value) return
  pendingFile.value = file
  showConfirmation('video')
}

async function uploadVideo() {
  const file = pendingFile.value
  if (!file || !canControl.value) return
  uploading.value = true
  previousResult = JSON.stringify(state.value?.result)
  awaitingResult.value = true
  error.value = ''
  busy.value = true
  const form = new FormData()
  form.append('file', file)
  try {
    state.value = await request('/source/video', { method: 'POST', body: form })
    streamView.value = 'auto'
    streamNonce.value = Date.now()
  } catch (exc) {
    awaitingResult.value = false
    error.value = exc.message
  } finally {
    uploading.value = false
    pendingFile.value = null
    busy.value = false
  }
}

function openSettings() {
  if (!canControl.value) return
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
  if (!canControl.value) return
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

function showConfirmation(kind) {
  returnFocus = document.activeElement
  confirmation.value = kind
}

function closeDialog() {
  if (busy.value) return
  settingsOpen.value = false
  confirmation.value = null
  pendingFile.value = null
}

async function confirmAction() {
  const kind = confirmation.value
  confirmation.value = null
  if (kind === 'video') await uploadVideo()
  if (kind === 'reset') await action('/stats/reset')
}

function dialogKeydown(event) {
  if (event.key === 'Escape') { event.preventDefault(); closeDialog() }
  if (event.key !== 'Tab') return
  const items = [...dialog.value.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), [tabindex="0"]')]
  if (!items.length) { event.preventDefault(); dialog.value.focus(); return }
  const first = items[0], last = items.at(-1)
  if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.value)) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.value)) { event.preventDefault(); first.focus() }
}

watch(() => settingsOpen.value || !!confirmation.value, async open => {
  if (open) {
    returnFocus = document.activeElement
    await nextTick()
    dialog.value?.focus()
  } else {
    await nextTick()
    returnFocus?.focus()
  }
})
watch(streamUrl, () => { streamFailed.value = false })
onMounted(async () => {
  freshnessTimer = setInterval(() => { clock.value = Date.now() }, 500)
  try { await session() } catch (exc) { error.value = exc.message }
  finally { sessionLoading.value = false }
})
onBeforeUnmount(() => {
  clearInterval(freshnessTimer)
  clearTimeout(reconnectTimer)
  clearInterval(heartbeatTimer)
  if (socket) { socket.onclose = null; socket.close() }
})
</script>

<template>
  <main v-if="authenticated && state" class="shell">
    <header class="topbar">
      <div class="brand"><div class="brand-mark">GP</div><div><h1>GearPro</h1><p>齿轮视觉检测</p></div></div>
      <div class="operation-status"><strong :class="{ running: connected && active }"><i></i>{{ runtimeLabel }}</strong><span>{{ sourceLabel }} · {{ state.settings.mode }}</span></div>
      <div class="top-actions">
        <span class="owner">控制权：{{ ownsControl ? '当前终端' : state.control.owner_label || '无人控制' }}</span>
        <button class="button" :disabled="!connected || busy" @click="ownsControl ? release() : acquire()">{{ ownsControl ? '释放控制' : '接管控制' }}</button>
        <button class="button quiet" :disabled="!canControl" @click="openSettings">设置</button>
        <button class="button quiet" @click="logout">退出</button>
      </div>
    </header>
    <div class="health-strip" aria-label="设备状态"><span v-for="item in healthItems" :key="item[0]" :class="['health-chip', { warning: item[1] === '失联' || item[1] === '未连接' }]"><i></i>{{ item[0] }}：{{ item[1] }}</span><span class="connection-note">{{ connected ? '设备状态持续更新' : '显示最后收到的数据' }}</span></div>
    <div v-if="!connected" class="alert warning" role="alert"><strong>{{ connectionLabel }}</strong><span>画面与判定可能已过期，控制操作暂不可用。系统正在自动恢复连接。</span></div>
    <div v-if="state.error" class="alert fault" role="alert"><strong>运行故障</strong><span>{{ state.error }}</span></div>
    <div v-if="error" class="alert fault" role="alert"><strong>操作失败</strong><span>{{ error }}</span><button class="button quiet" @click="error = ''">关闭</button></div>
    <section class="workspace">
      <article class="vision-panel">
        <div class="panel-head"><div><h2>{{ state.source.type === 'video' ? '测试视频画面' : '检测画面' }}</h2><span>{{ sourceLabel }}</span></div><div class="segmented" aria-label="画面显示模式"><button v-for="view in [['auto','自动'],['raw','原图'],['annotated','标注']]" :key="view[0]" :aria-pressed="streamView === view[0]" :class="{ active: streamView === view[0] }" @click="streamView = view[0]">{{ view[1] }}</button></div></div>
        <div :class="['video-stage', { stale: !connected }]">
          <img :key="streamNonce" :src="streamUrl" alt="齿轮检测画面" @error="streamFailed = true" @load="streamFailed = false" />
          <span class="frame-status">{{ !connected ? '连接失效 · 历史画面' : !active && streamView === 'annotated' ? '上次标注画面' : streamView === 'raw' ? '原始画面' : runtimeLabel }}</span>
          <div v-if="streamFailed" class="empty-frame"><strong>暂无检测画面</strong><span>{{ state.source.type === 'video' ? '请检查测试视频，或返回实时相机' : '请检查相机连接及画面输出' }}</span><button class="button" :disabled="!connected" @click="streamNonce = Date.now()">重新加载画面</button></div>
        </div>
        <div class="control-row">
          <button :class="['button', 'large', active ? 'stop' : 'primary']" :disabled="!canControl || !!startBlocked" @click="action(active ? '/inspection/stop' : '/inspection/start')"><span aria-hidden="true">{{ active ? '■' : '▶' }}</span>{{ busy && !uploading ? '正在处理…' : active ? '停止检测' : '开始检测' }}</button>
          <span class="control-help">{{ startBlocked || state.status }}</span>
          <input ref="uploadInput" hidden type="file" accept="video/*,.mkv" @change="chooseVideo" />
          <button class="button quiet" :disabled="!canControl" @click="uploadInput.click()">{{ uploading ? '正在上传视频…' : '测试视频…' }}</button>
          <button v-if="state.source.type === 'video'" class="button" :disabled="!canControl" @click="action('/source/camera')">返回实时相机</button>
        </div>
      </article>
      <aside class="side-stack">
        <section class="result-panel">
          <div class="section-heading"><h2>{{ historical && result ? '上次检测结果' : '当前检测结果' }}</h2><span>{{ !connected ? '数据已失效' : !active && result ? '检测已停止' : '最近一次判定' }}</span></div>
          <div :class="['important-verdict', verdictClass]" aria-live="polite"><span class="verdict-symbol" aria-hidden="true">{{ verdictClass === 'good' ? '✓' : verdictClass === 'bad' ? '×' : '—' }}</span><strong>{{ verdictLabel }}</strong></div>
          <p v-if="historical || !result?.has_gear" class="result-note">{{ !connected ? '连接恢复前，请勿将历史判定视为当前结果。' : !active && result ? '保留停止前的判定，开始检测后等待新结果。' : '等待齿轮进入检测区域' }}</p>
          <div class="result-values"><div><span>缺陷类型</span><strong>{{ result?.has_gear ? rejectReason : '—' }}</strong></div><div><span>定位齿轮数</span><strong>{{ result?.observations?.length ?? 0 }} <small>个</small></strong></div></div>
        </section>
        <section class="stats-panel">
          <div class="section-heading"><h2>质量统计</h2><button class="button quiet compact" :disabled="!canControl" @click="showConfirmation('reset')">清空统计</button></div>
          <div class="stats-summary"><div><span>累计检测</span><strong>{{ state.stats.total }}</strong></div><div><span>合格</span><strong>{{ state.stats.good }}</strong></div><div class="bad"><span>不合格</span><strong>{{ state.stats.defective }}</strong></div></div>
          <div class="rate-row"><span>累计合格率</span><strong>{{ goodRate }}</strong></div>
          <svg class="quality-chart" viewBox="0 0 100 7" preserveAspectRatio="none" role="img" :aria-label="`累计合格率 ${goodRate}`"><rect class="chart-track" width="100" height="7" rx="1"/><rect class="chart-good" :width="goodRateValue" height="7" rx="1"/></svg>
          <div class="defect-breakdown"><p>不合格分类 <span>占不合格判定比例</span></p><div v-for="item in [['scratch','划痕'],['missing_hole','缺齿 / 缺口'],['combined','同时命中']]" :key="item[0]" class="breakdown-row"><span>{{ item[1] }}</span><svg viewBox="0 0 100 5" preserveAspectRatio="none" aria-hidden="true"><rect class="chart-track" width="100" height="5"/><rect class="breakdown-value" :width="defectShareValue(item[0])" height="5"/></svg><strong>{{ state.stats[item[0]] || 0 }}</strong></div></div>
        </section>
        <details class="inference-panel"><summary>推理详情<span>概率、阈值与耗时</span></summary><div class="inference-body"><p class="model-version">模型：{{ modelVersions }}</p>
          <div class="probability-list"><div v-for="item in [['划痕', scratchProbability, state.settings.scratch_threshold], ['缺齿 / 缺口', missingHoleProbability, state.settings.missing_hole_threshold]]" :key="item[0]"><span>{{ item[0] }}</span><strong>{{ formatProbability(item[1]) }}</strong><svg class="probability-chart" viewBox="0 0 100 6" preserveAspectRatio="none" aria-hidden="true"><rect class="chart-track" width="100" height="6"/><rect class="chart-value" :width="item[1] === null ? 0 : Math.min(100, item[1] * 100)" height="6"/><line class="chart-threshold" :x1="item[2] * 100" :x2="item[2] * 100" y1="0" y2="6"/></svg><small>阈值 {{ item[2].toFixed(6) }}</small></div></div>
          <div class="detail-grid"><div><span>总耗时</span><b>{{ formatMs(result?.elapsed_ms) }}</b></div><div><span>定位阶段</span><b>{{ formatMs(result?.timings?.locator_ms) }}</b></div><div><span>划痕阶段</span><b>{{ formatMs(result?.timings?.scratch?.total_ms) }}</b></div><div><span>缺口阶段</span><b>{{ formatMs(result?.timings?.missing_hole?.total_ms) }}</b></div></div></div></details>
      </aside>
    </section>
    <footer><span>运行模式：{{ state.settings.mode }}</span><span>推理档位：{{ state.settings.inference_profile }}</span><span>统计按现有检测计数规则累计</span></footer>
  </main>
  <main v-else-if="sessionLoading || authenticated" class="login-page"><section class="login-card" aria-live="polite"><div class="brand-mark">GP</div><h1>{{ authenticated ? connectionLabel : '正在连接控制台' }}</h1><p>正在获取设备状态，请稍候。</p><p v-if="error" class="form-error">{{ error }}</p><button v-if="authenticated" class="button" @click="logout">返回登录</button></section></main>
  <main v-else class="login-page"><form class="login-card" @submit.prevent="login"><div class="brand-mark">GP</div><h1>GearPro 控制台</h1><p>连接齿轮视觉检测系统</p><label>终端名称<input v-model="label" required maxlength="64"/></label><label v-if="passwordRequired">访问密码<input v-model="password" type="password" required autocomplete="current-password"/></label><div v-if="error" class="form-error" role="alert">{{ error }}</div><button class="button primary large" :disabled="busy">{{ busy ? '正在连接…' : '进入控制台' }}</button></form></main>

  <div v-if="settingsOpen || confirmation" class="modal" @click.self="closeDialog" @keydown="dialogKeydown">
    <section ref="dialog" class="dialog-card" :class="{ 'settings-card': settingsOpen }" role="dialog" aria-modal="true" aria-labelledby="dialog-title" tabindex="-1">
      <form v-if="settingsOpen" @submit.prevent="saveSettings">
        <div class="settings-title"><div><h2 id="dialog-title">运行设置</h2><p>调整任务、判定参数及设备连接</p></div><button type="button" class="button quiet" :disabled="busy" @click="closeDialog">关闭</button></div>
        <fieldset :disabled="!canControl"><legend>运行任务</legend><div class="form-grid">
          <label>运行模式<select v-model="settings.mode"><option>自由模式</option><option>定量模式</option><option>定时模式</option><option v-if="settings.mode === '视频测试模式'">视频测试模式</option></select></label>
          <label>推理档位<select v-model="settings.inference_profile"><option value="FULL">完整检测（FULL）</option><option value="SPARSE">稀疏检测（SPARSE）</option><option value="SAFE_STOP">安全停止（SAFE_STOP）</option></select></label>
          <label v-if="settings.mode === '定量模式'">目标数量<input v-model.number="settings.target_quantity" type="number" min="1" required/></label>
          <label v-if="settings.mode === '定时模式'">运行时长（分钟）<input v-model.number="settings.duration_minutes" type="number" min="1" required/></label>
          <label>推理间隔（秒）<input v-model.number="settings.inference_interval" type="number" min="0.03" max="5" step="0.01" required/></label>
        </div></fieldset>
        <fieldset :disabled="!canControl"><legend>判定参数</legend><div class="form-grid"><label>齿轮定位阈值<input v-model.number="settings.locator_confidence" type="number" min="0.01" max="0.99" step="0.01" required/></label><label>划痕判定阈值<input v-model.number="settings.scratch_threshold" type="number" min="0.01" max="0.99" step="0.000001" required/></label><label>缺齿 / 缺口阈值<input v-model.number="settings.missing_hole_threshold" type="number" min="0.01" max="0.99" step="0.000001" required/></label></div><button type="button" class="button quiet" @click="resetThresholds">恢复模型默认阈值</button></fieldset>
        <fieldset :disabled="!canControl"><legend>设备与画面</legend><div class="form-grid"><label>摄像头索引<input v-model.number="settings.camera_index" type="number" min="0" max="32" required/></label><label>串口设备<input v-model="settings.serial_port" required/></label><label>串口波特率<input v-model.number="settings.serial_baudrate" type="number" min="300" required/></label><label>画面帧率<input v-model.number="settings.stream_fps" type="number" min="1" max="30" required/></label><label>JPEG 质量<input v-model.number="settings.stream_quality" type="number" min="30" max="95" required/></label></div></fieldset>
        <p v-if="!connected || !ownsControl" class="form-error">连接恢复且拥有控制权后可保存设置。</p><p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <div class="settings-actions"><button type="button" class="button" :disabled="busy" @click="closeDialog">取消</button><button class="button primary" :disabled="!canControl">{{ busy ? '正在保存…' : '保存设置' }}</button></div>
      </form>
      <template v-else><h2 id="dialog-title">{{ confirmation === 'video' ? '切换到测试视频？' : '清空检测统计？' }}</h2><p>{{ confirmation === 'video' ? '将停止当前检测，切换来源并开始检测所选视频。测试期间相机和串口不参与检测。' : '将清除累计统计、最近检测结果和标注画面。此操作无法撤销。' }}</p><p v-if="pendingFile" class="filename">{{ pendingFile.name }}</p><div class="settings-actions"><button class="button" @click="closeDialog">取消</button><button class="button primary" :disabled="!canControl" @click="confirmAction">{{ confirmation === 'video' ? '切换并开始检测' : '确认清空' }}</button></div></template>
    </section>
  </div>
</template>
