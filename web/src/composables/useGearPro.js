import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const API = '/api/v2'
const HISTORY_SIZE = 12

function duration(seconds) {
  if (!Number.isFinite(seconds)) return '—'
  const total = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(total / 3600)
  const clock = [Math.floor(total / 60) % 60, total % 60].map(value => String(value).padStart(2, '0')).join(':')
  return hours ? `${hours}:${clock}` : clock
}

export function useGearPro() {
  const state = ref(null)
  const authenticated = ref(false)
  const sessionLoading = ref(true)
  const passwordRequired = ref(true)
  const password = ref('')
  const label = ref(localStorage.getItem('gearpro-terminal') || `终端 ${location.hostname}`)
  const error = ref('')
  const busy = ref(false)
  const operation = ref('')
  const connection = ref('connecting')
  const clock = ref(Date.now())
  const lastMessageAt = ref(0)
  const awaitingResult = ref(false)
  const streamView = ref('auto')
  const streamNonce = ref(Date.now())
  const history = ref([])
  let previousResult = ''
  let historyKey = ''
  let historyId = 0
  let socket, reconnectTimer, tickTimer, heartbeatTimer

  const connected = computed(() => connection.value === 'connected' && clock.value - lastMessageAt.value < 5000)
  const ownsControl = computed(() => state.value?.control?.is_owner === true)
  const active = computed(() => state.value?.inspection?.active === true)
  const canControl = computed(() => connected.value && ownsControl.value && !busy.value)
  const result = computed(() => awaitingResult.value ? null : state.value?.result)
  const historical = computed(() => !connected.value || !active.value)
  const isVideo = computed(() => state.value?.source?.type === 'video')
  const isReplay = computed(() => state.value?.source?.type === 'replay')
  const offlineSource = computed(() => isVideo.value || isReplay.value)
  const sourceLabel = computed(() => {
    if (isVideo.value) return `测试视频：${state.value.source.video_name}`
    if (isReplay.value) return '数据集回放'
    return `实时相机 ${state.value?.settings?.camera_index ?? ''}`
  })
  const connectionLabel = computed(() => connected.value ? '已连接' : connection.value === 'connected' ? '状态更新超时' : connection.value === 'reconnecting' ? '正在重新连接' : '正在连接设备')
  const runtimeLabel = computed(() => !connected.value ? connectionLabel.value : state.value?.error ? '检测故障' : active.value ? '检测运行中' : state.value?.status === '当前任务已完成' ? '任务已完成' : '检测已停止')
  const startBlocked = computed(() => {
    if (!connected.value) return '连接恢复后可操作'
    if (!ownsControl.value) return '请先接管控制'
    if (active.value) return '检测正在运行'
    if (state.value?.settings?.inference_profile === 'SAFE_STOP') return '请在设置中退出安全停止档位'
    if (!offlineSource.value && !state.value?.health?.camera?.opened) return '相机未连接，请检查设备'
    return ''
  })
  const verdictClass = computed(() => historical.value || !result.value?.has_gear ? 'idle' : result.value.is_defective ? 'bad' : 'good')
  const verdictLabel = computed(() => result.value?.verdict || (active.value ? '等待结果' : '等待开始'))
  const rejectReason = computed(() => {
    const labels = { scratch: '划痕', missing_hole: '缺齿 / 缺口' }
    return result.value?.reject_reasons?.map(reason => labels[reason] || reason).join('、') || '未命中缺陷'
  })
  const goodRate = computed(() => state.value?.stats?.total ? `${((state.value.stats.good_rate || 0) * 100).toFixed(1)}%` : '—')
  const healthItems = computed(() => [
    ['相机', offlineSource.value ? '未使用' : !connected.value ? '未知' : state.value?.health?.camera?.opened ? '已连接' : '未连接'],
    ['模型', !connected.value ? '未知' : state.value?.inspection?.model_loaded ? '已加载' : '待加载'],
    ['串口', offlineSource.value ? '未使用' : !connected.value ? '未知' : state.value?.health?.serial?.connected ? '已连接' : '未连接'],
  ])
  const streamUrl = computed(() => `${API}/stream?view=${streamView.value}&v=${streamNonce.value}`)
  const task = computed(() => {
    const current = state.value
    if (!current) return null
    const elapsed = current.inspection?.started_seconds_ago
    if (current.settings.mode === '定量模式') {
      const target = current.settings.target_quantity
      return { label: '目标进度', ratio: target ? current.stats.total / target : null, text: `${current.stats.total} / ${target}` }
    }
    if (current.settings.mode === '定时模式') {
      const limit = current.settings.duration_minutes * 60
      return { label: '计时进度', ratio: Number.isFinite(elapsed) ? elapsed / limit : 0, text: `${duration(elapsed ?? 0)} / ${duration(limit)}` }
    }
    return { label: '运行时长', ratio: null, text: active.value ? duration(elapsed) : '—' }
  })

  function specialist(name) {
    const readings = (result.value?.observations || [])
      .map(item => item.specialists?.[name])
      .filter(item => Number.isFinite(item?.probability))
    if (!readings.length) return null
    const top = readings.reduce((best, item) => item.probability > best.probability ? item : best)
    const threshold = top.threshold ?? state.value?.settings?.[`${name}_threshold`]
    return { probability: top.probability, threshold, reject: top.reject ?? top.probability >= threshold }
  }

  function recordHistory() {
    const current = state.value
    if (!current?.stats?.total) { history.value = []; historyKey = ''; return }
    const latest = current.result
    const key = latest ? JSON.stringify(latest) : ''
    if (key === historyKey) return
    historyKey = key
    if (!current.inspection?.active || !latest?.has_gear) return
    history.value = [{ id: ++historyId, bad: !!latest.is_defective, verdict: latest.verdict, reasons: latest.reject_reasons || [] }, ...history.value].slice(0, HISTORY_SIZE)
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

  function waitForNewResult() {
    previousResult = JSON.stringify(state.value?.result)
    awaitingResult.value = true
  }

  function connect() {
    clearTimeout(reconnectTimer)
    if (socket) { socket.onclose = null; socket.close() }
    connection.value = state.value ? 'reconnecting' : 'connecting'
    socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${API}/events`)
    socket.onmessage = event => {
      try {
        state.value = JSON.parse(event.data)
        if (awaitingResult.value && JSON.stringify(state.value.result) !== previousResult) awaitingResult.value = false
        recordHistory()
        lastMessageAt.value = clock.value = Date.now()
        connection.value = 'connected'
      } catch { error.value = '无法读取设备状态，请重新连接' }
    }
    socket.onclose = event => {
      connection.value = 'reconnecting'
      if (event.code === 4401) { authenticated.value = false; state.value = null; return }
      if (authenticated.value) reconnectTimer = setTimeout(connect, 1500)
    }
  }

  async function login() {
    error.value = ''
    busy.value = true
    try {
      await request('/session/login', { method: 'POST', body: JSON.stringify({ password: password.value, label: label.value }) })
      localStorage.setItem('gearpro-terminal', label.value)
      password.value = ''
      authenticated.value = true
      connect()
    } catch (exc) { error.value = exc.message }
    finally { busy.value = false }
  }

  async function logout() {
    authenticated.value = false
    clearTimeout(reconnectTimer)
    if (socket) { socket.onclose = null; socket.close() }
    state.value = null
    awaitingResult.value = false
    await request('/session/logout', { method: 'POST' }).catch(() => {})
  }

  async function action(path, body) {
    if (!connected.value || busy.value || (!ownsControl.value && path !== '/control/acquire')) return false
    if (path === '/inspection/start' && startBlocked.value) return false
    if (path === '/inspection/stop' && !active.value) return false
    error.value = ''
    busy.value = true
    operation.value = path
    if (path === '/inspection/start' || path === '/source/camera') waitForNewResult()
    try {
      const payload = await request(path, { method: body === undefined ? 'POST' : 'PUT', body: body === undefined ? undefined : JSON.stringify(body) })
      if (payload?.version) state.value = payload
      if (path === '/source/camera') { streamView.value = 'auto'; streamNonce.value = Date.now() }
      return true
    } catch (exc) { awaitingResult.value = false; error.value = exc.message; return false }
    finally { busy.value = false; operation.value = '' }
  }

  async function uploadVideo(file) {
    if (!file || !canControl.value) return false
    error.value = ''
    busy.value = true
    operation.value = '/source/video'
    waitForNewResult()
    const form = new FormData()
    form.append('file', file)
    try {
      state.value = await request('/source/video', { method: 'POST', body: form })
      streamView.value = 'auto'
      streamNonce.value = Date.now()
      return true
    } catch (exc) { awaitingResult.value = false; error.value = exc.message; return false }
    finally { busy.value = false; operation.value = '' }
  }

  onMounted(async () => {
    tickTimer = setInterval(() => { clock.value = Date.now() }, 500)
    heartbeatTimer = setInterval(() => {
      if (authenticated.value && ownsControl.value && socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'control_heartbeat' }))
    }, 10000)
    try {
      const info = await request('/session')
      passwordRequired.value = info.password_required
      authenticated.value = info.authenticated
      if (info.authenticated) connect()
      else if (!info.password_required) await login()
    } catch (exc) { error.value = exc.message }
    finally { sessionLoading.value = false }
  })
  onBeforeUnmount(() => {
    clearInterval(tickTimer)
    clearInterval(heartbeatTimer)
    clearTimeout(reconnectTimer)
    if (socket) { socket.onclose = null; socket.close() }
  })
  return { state, authenticated, sessionLoading, passwordRequired, password, label, error, busy, operation,
    connected, ownsControl, active, canControl, result, historical, isVideo, sourceLabel, connectionLabel,
    runtimeLabel, startBlocked, verdictClass, verdictLabel, rejectReason, goodRate, healthItems,
    streamView, streamNonce, streamUrl, task, history, historySize: HISTORY_SIZE, specialist,
    action, uploadVideo, login, logout }
}
