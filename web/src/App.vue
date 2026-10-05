<script setup>
import { computed, reactive, ref } from 'vue'
import { useGearPro } from './composables/useGearPro.js'
import DialogShell from './components/DialogShell.vue'
import CameraView from './components/CameraView.vue'
import DetectionPage from './pages/DetectionPage.vue'
import StatisticsPage from './pages/StatisticsPage.vue'
import VideoPage from './pages/VideoPage.vue'
import SettingsPage from './pages/SettingsPage.vue'

const controller = reactive(useGearPro())
const page = ref('detection')
const settingsDirty = ref(false)
const confirmation = ref(null)
const enlarged = ref(false)
const pendingFile = ref(null)
const destination = ref(null)
const navigation = [
  ['detection', '检测', '▣'],
  ['statistics', '统计', '▥'],
  ['video', '视频测试', '▷'],
  ['settings', '设置', '⚙'],
]
const pageTitle = computed(() => navigation.find(item => item[0] === page.value)?.[1])
const dialogTitle = computed(() => ({
  video: '切换到测试视频？',
  reset: '清空检测统计？',
  discard: '放弃未保存修改？',
})[confirmation.value])

function navigate(target) {
  if (target === page.value || controller.busy) return
  if (page.value === 'settings' && settingsDirty.value) {
    destination.value = target
    confirmation.value = 'discard'
    return
  }
  switchPage(target)
}
function switchPage(target) {
  settingsDirty.value = false
  if (target === 'logout') { controller.logout(); page.value = 'detection' }
  else page.value = target
}
function selectVideo(file) {
  if (!controller.canControl) return
  pendingFile.value = file
  confirmation.value = 'video'
}
function closeConfirmation() {
  if (controller.busy) return
  confirmation.value = null
  pendingFile.value = null
  destination.value = null
}
async function confirmAction() {
  const kind = confirmation.value
  if (kind !== 'discard' && !controller.canControl) return
  if (kind === 'discard') {
    const target = destination.value
    closeConfirmation()
    switchPage(target)
    return
  }
  if (kind === 'video' && await controller.uploadVideo(pendingFile.value)) {
    closeConfirmation()
    switchPage('detection')
  } else if (kind === 'reset' && await controller.action('/stats/reset')) closeConfirmation()
}
async function returnToCamera() {
  if (await controller.action('/source/camera')) switchPage('detection')
}
</script>

<template>
  <main v-if="controller.authenticated && controller.state" class="console-shell" :inert="!!confirmation || enlarged">
    <aside class="function-rail">
      <div class="rail-brand"><span class="brand-mark">GP</span><div><strong>GearPro</strong><small>齿轮视觉检测</small></div></div>
      <div class="inspection-controls" aria-label="检测控制">
        <button class="rail-button start-button" :disabled="!controller.canControl || !!controller.startBlocked" :title="controller.startBlocked" @click="controller.action('/inspection/start')"><span aria-hidden="true">▶</span>开始检测</button>
        <button class="rail-button stop-button" :disabled="!controller.canControl || !controller.active" @click="controller.action('/inspection/stop')"><span aria-hidden="true">■</span>停止检测</button>
      </div>
      <nav class="page-navigation" aria-label="功能导航">
        <button v-for="[key, title, icon] in navigation" :key="key" :class="['rail-button', { selected: page === key }]" :aria-current="page === key ? 'page' : undefined" :disabled="controller.busy" @click="navigate(key)"><span aria-hidden="true">{{ icon }}</span>{{ title }}</button>
      </nav>
      <div class="rail-account">
        <p class="owner-label">控制权：{{ controller.ownsControl ? '当前终端' : controller.state.control.owner_label || '无人控制' }}</p>
        <button class="rail-button" :disabled="!controller.connected || controller.busy" @click="controller.action(controller.ownsControl ? '/control/release' : '/control/acquire')">{{ controller.ownsControl ? '释放控制' : '接管控制' }}</button>
        <button class="rail-button exit-button" :disabled="controller.busy" @click="navigate('logout')">退出登录</button>
      </div>
    </aside>

    <div class="console-main">
      <header class="system-header">
        <div class="runtime-reading"><strong :class="{ running: controller.connected && controller.active, fault: controller.state.error || !controller.connected }"><i></i>{{ controller.runtimeLabel }}</strong><span>{{ controller.state.settings.mode }}</span></div>
        <div class="device-strip" aria-label="设备状态"><span v-for="[device, status] in controller.healthItems" :key="device" :class="{ warning: status === '未连接' || status === '未知' }">{{ device }}：{{ status }}</span></div>
        <div class="source-line"><span>{{ controller.sourceLabel }}</span><span>{{ pageTitle }}</span></div>
      </header>
      <div v-if="!controller.connected || controller.state.error || controller.error" class="alert-stack" role="alert">
        <p v-if="!controller.connected"><strong>{{ controller.connectionLabel }}</strong> · 数据可能过期，连接恢复后可操作。</p>
        <p v-if="controller.state.error"><strong>运行故障：</strong>{{ controller.state.error }}</p>
        <div v-if="controller.error"><p><strong>操作失败：</strong>{{ controller.error }}</p><button class="button" @click="controller.error = ''">关闭</button></div>
      </div>
      <div class="page-content">
        <DetectionPage v-if="page === 'detection'" :controller="controller" :enlarged="enlarged" @enlarge="enlarged = true" />
        <StatisticsPage v-else-if="page === 'statistics'" :controller="controller" @reset="confirmation = 'reset'" />
        <VideoPage v-else-if="page === 'video'" :controller="controller" @video="selectVideo" @camera="returnToCamera" />
        <SettingsPage v-else :controller="controller" @dirty="settingsDirty = $event" />
      </div>
      <p class="operation-hint" role="status">{{ controller.busy ? (controller.operation === '/source/video' ? '正在上传并准备测试视频…' : '正在处理操作…') : controller.active ? controller.state.status : controller.startBlocked || controller.state.status }}</p>
    </div>
  </main>

  <main v-else-if="controller.sessionLoading || controller.authenticated" class="login-page">
    <section class="login-panel" aria-live="polite"><div class="brand-mark">GP</div><h1>{{ controller.authenticated ? controller.connectionLabel : '正在连接控制台' }}</h1><p>正在获取设备状态，请稍候。</p><p v-if="controller.error" class="form-error">{{ controller.error }}</p><button v-if="controller.authenticated" class="button" @click="controller.logout">返回登录</button></section>
  </main>
  <main v-else class="login-page">
    <form class="login-panel" @submit.prevent="controller.login"><div class="brand-mark">GP</div><h1>GearPro 控制台</h1><p>齿轮视觉检测系统</p><label>终端名称<input v-model="controller.label" required maxlength="64" /></label><label v-if="controller.passwordRequired">访问密码<input v-model="controller.password" type="password" required autocomplete="current-password" /></label><p v-if="controller.error" class="form-error" role="alert">{{ controller.error }}</p><button class="button primary" :disabled="controller.busy">{{ controller.busy ? '正在连接…' : '进入控制台' }}</button></form>
  </main>

  <DialogShell v-if="confirmation && controller.authenticated" :title="dialogTitle" :busy="controller.busy" @close="closeConfirmation">
    <p class="dialog-copy">{{ confirmation === 'video' ? '将停止当前检测，切换来源并开始检测所选视频。测试期间相机和串口不参与检测。' : confirmation === 'reset' ? '将清除累计统计、最近检测结果和标注画面。此操作无法撤销。' : '尚有未保存的设置，离开后将丢弃这些修改。' }}</p>
    <p v-if="pendingFile" class="filename">{{ pendingFile.name }}</p>
    <p v-if="controller.error" class="form-error" role="alert">{{ controller.error }}</p>
    <div class="dialog-actions"><button class="button" :disabled="controller.busy" @click="closeConfirmation">取消</button><button class="button primary" :disabled="controller.busy || (confirmation !== 'discard' && !controller.canControl)" @click="confirmAction">{{ controller.busy ? '正在处理…' : confirmation === 'video' ? '切换并开始检测' : confirmation === 'reset' ? '确认清空' : '放弃并离开' }}</button></div>
  </DialogShell>
  <DialogShell v-if="enlarged && controller.authenticated" title="检测画面" wide restore-selector=".enlarge-button" @close="enlarged = false">
    <CameraView :controller="controller" @enlarge="enlarged = false" />
  </DialogShell>
</template>
