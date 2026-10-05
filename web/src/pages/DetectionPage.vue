<script setup>
import { computed } from 'vue'
import CameraView from '../components/CameraView.vue'
import StatsStrip from '../components/StatsStrip.vue'
const props = defineProps({ controller: Object, enlarged: Boolean })
defineEmits(['enlarge'])
const specialists = [['scratch', '划痕'], ['missing_hole', '缺齿 / 缺口']]
const reasonLabels = { scratch: '划痕', missing_hole: '缺齿 / 缺口' }
const emptySlots = computed(() => Math.max(0, props.controller.historySize - props.controller.history.length))
const historyBad = computed(() => props.controller.history.filter(item => item.bad).length)
const percent = value => Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : '—'
const bounded = value => `${Math.max(0, Math.min(100, (value || 0) * 100))}%`
const elapsed = computed(() => {
  const value = props.controller.result?.elapsed_ms
  return Number.isFinite(value) ? `${value.toFixed(0)} ms` : '—'
})
const historyTitle = item => item.bad ? `不合格：${item.reasons.map(reason => reasonLabels[reason] || reason).join('、') || '缺陷'}` : '合格'
</script>

<template>
  <div class="detection-page">
    <div class="camera-column">
      <CameraView v-if="!enlarged" :controller="controller" @enlarge="$emit('enlarge')" />
      <div v-else class="camera-placeholder">画面已放大显示</div>
      <section class="history-panel" aria-label="最近判定">
        <header><h2>最近判定</h2><span>{{ controller.history.length ? `${controller.history.length} 件 · 不合格 ${historyBad}` : '暂无记录' }}</span></header>
        <ol class="history-track">
          <li v-for="item in controller.history" :key="item.id" :class="item.bad ? 'bad' : 'good'" :title="historyTitle(item)"><span aria-hidden="true">{{ item.bad ? '×' : '✓' }}</span><span class="sr-only">{{ historyTitle(item) }}</span></li>
          <li v-for="slot in emptySlots" :key="`empty-${slot}`" class="empty" aria-hidden="true"></li>
        </ol>
      </section>
    </div>

    <div class="result-column">
      <section :class="['verdict-panel', controller.verdictClass]" aria-live="polite">
        <h2>{{ controller.historical && controller.result ? '上次检测结果' : '当前判定' }}</h2>
        <div class="verdict-value"><span class="verdict-icon" aria-hidden="true">{{ controller.verdictClass === 'good' ? '✓' : controller.verdictClass === 'bad' ? '×' : '—' }}</span><strong>{{ controller.verdictLabel }}</strong></div>
        <p v-if="controller.historical && controller.result" class="verdict-note">{{ controller.connected ? '检测已停止，保留上次结果' : '连接失效，结果仅供参考' }}</p>
        <p class="verdict-reason"><span>缺陷原因</span><strong>{{ controller.result?.has_gear ? controller.rejectReason : '—' }}</strong></p>
      </section>

      <section class="probe-panel" aria-label="本次检测详情">
        <h2>本次检测</h2>
        <div v-for="[name, title] in specialists" :key="name" :class="['probe', { bad: controller.specialist(name)?.reject }]">
          <div class="probe-label"><span>{{ title }}</span><strong>{{ percent(controller.specialist(name)?.probability) }}</strong></div>
          <div class="meter" role="meter" :aria-label="`${title}概率`" aria-valuemin="0" aria-valuemax="1" :aria-valuenow="controller.specialist(name)?.probability ?? 0">
            <i :style="{ width: bounded(controller.specialist(name)?.probability) }"></i>
            <b v-if="Number.isFinite(controller.specialist(name)?.threshold ?? controller.state.settings[`${name}_threshold`])" :style="{ left: bounded(controller.specialist(name)?.threshold ?? controller.state.settings[`${name}_threshold`]) }" title="判定阈值"></b>
          </div>
        </div>
        <dl class="fact-row">
          <div><dt>定位齿轮</dt><dd>{{ controller.result?.observations?.length ?? 0 }} 个</dd></div>
          <div><dt>单帧耗时</dt><dd>{{ elapsed }}</dd></div>
          <div><dt>{{ controller.task.label }}</dt><dd>{{ controller.task.text }}</dd></div>
        </dl>
      </section>
    </div>

    <StatsStrip class="detection-stats" :controller="controller" />
  </div>
</template>
