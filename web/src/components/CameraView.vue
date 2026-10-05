<script setup>
import { ref, watch } from 'vue'
const props = defineProps({ controller: Object })
defineEmits(['enlarge'])
const failed = ref(false)
watch(() => props.controller.streamUrl, () => { failed.value = false })
</script>

<template>
  <section class="camera-panel">
    <header class="camera-heading">
      <h2>{{ controller.isVideo ? '测试画面' : '检测画面' }}</h2>
      <div class="view-switch" aria-label="画面显示模式">
        <button v-for="view in [['auto','自动'],['raw','原图'],['annotated','标注']]" :key="view[0]" :aria-pressed="controller.streamView === view[0]" @click="controller.streamView = view[0]">{{ view[1] }}</button>
      </div>
    </header>
    <div :class="['camera-stage', { stale: !controller.connected }]">
      <img :src="controller.streamUrl" :key="controller.streamNonce" alt="齿轮检测画面" @error="failed = true" @load="failed = false" />
      <span v-if="!controller.connected || (!controller.active && controller.streamView === 'annotated')" class="frame-note">{{ !controller.connected ? '连接失效 · 历史画面' : '上次标注画面' }}</span>
      <div v-if="failed" class="camera-empty"><strong>暂无画面</strong><p>请检查{{ controller.isVideo ? '测试视频' : '相机连接' }}</p><button class="button" :disabled="!controller.connected" @click="controller.streamNonce = Date.now()">重新加载</button></div>
    </div>
    <button class="enlarge-button" @click="$emit('enlarge')">放大画面</button>
  </section>
</template>
