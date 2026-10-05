<script setup>
defineProps({ controller: Object })
const emit = defineEmits(['video', 'camera'])
function choose(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (file) emit('video', file)
}
</script>
<template>
  <div class="scroll-page video-page">
    <header class="page-heading"><h1>视频测试</h1></header>
    <section class="section-block video-intro"><h2>使用视频验证检测效果</h2><p>选择视频后，确认切换来源并开始检测。测试期间相机和串口不参与检测。</p><p class="source-reading">当前来源：{{ controller.sourceLabel }}</p>
      <label class="file-picker">选择测试视频<input type="file" accept="video/*,.mkv" :disabled="!controller.canControl" @change="choose" /></label>
      <p v-if="!controller.canControl" class="muted">{{ controller.connected ? '请先接管控制' : '连接恢复后可选择视频' }}</p>
      <p v-if="controller.operation === '/source/video'" role="status">正在上传并准备检测，请稍候…</p>
      <button v-if="controller.isVideo" class="button" :disabled="!controller.canControl" @click="$emit('camera')">返回实时相机</button>
    </section>
  </div>
</template>
