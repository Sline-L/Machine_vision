<script setup>
import CameraView from '../components/CameraView.vue'
import StatsStrip from '../components/StatsStrip.vue'
defineProps({ controller: Object, enlarged: Boolean })
defineEmits(['enlarge'])
</script>
<template>
  <div class="detection-page">
    <div class="inspection-main">
      <CameraView v-if="!enlarged" :controller="controller" @enlarge="$emit('enlarge')" />
      <section :class="['verdict-panel', controller.verdictClass]" aria-live="polite">
        <h2>{{ controller.historical && controller.result ? '上次检测结果' : '当前判定' }}</h2>
        <div class="verdict-value"><span aria-hidden="true">{{ controller.verdictClass === 'good' ? '✓' : controller.verdictClass === 'bad' ? '×' : '—' }}</span><strong>{{ controller.verdictLabel }}</strong></div>
        <p v-if="controller.historical && controller.result" class="verdict-note">{{ controller.connected ? '检测已停止，保留上次结果' : '连接失效，结果仅供参考' }}</p>
        <dl class="verdict-details"><div><dt>缺陷原因</dt><dd>{{ controller.result?.has_gear ? controller.rejectReason : '—' }}</dd></div><div><dt>定位齿轮</dt><dd>{{ controller.result?.observations?.length ?? 0 }} 个</dd></div></dl>
      </section>
    </div>
    <StatsStrip :controller="controller" />
  </div>
</template>
