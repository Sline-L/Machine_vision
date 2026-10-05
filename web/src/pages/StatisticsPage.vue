<script setup>
import { computed } from 'vue'
import RingGauge from '../components/RingGauge.vue'
const props = defineProps({ controller: Object })
defineEmits(['reset'])
const categories = [['scratch', '划痕'], ['missing_hole', '缺齿 / 缺口'], ['combined', '同时命中']]
const stats = computed(() => props.controller.state.stats)
const ofTotal = value => stats.value.total ? value / stats.value.total : null
const ofDefective = name => stats.value.defective ? (stats.value[name] || 0) / stats.value.defective : null
const task = computed(() => props.controller.task)
function probability(name) {
  const values = props.controller.result?.observations?.map(item => item.specialists?.[name]?.probability).filter(Number.isFinite) || []
  return values.length ? `${(Math.max(...values) * 100).toFixed(2)}%` : '—'
}
const ms = value => Number.isFinite(value) ? `${value.toFixed(1)} ms` : '—'
</script>

<template>
  <div class="scroll-page statistics-page">
    <header class="page-heading"><h1>检测统计</h1><span>累计 {{ stats.total }} 件</span><button class="button" :disabled="!controller.canControl" @click="$emit('reset')">清空统计</button></header>

    <section class="section-block">
      <h2>总体质量</h2>
      <div class="ring-row overall-rings">
        <RingGauge title="合格率" tone="good" :ratio="ofTotal(stats.good)" :detail="`合格 ${stats.good} 件`" />
        <RingGauge title="不合格率" tone="bad" :ratio="ofTotal(stats.defective)" :detail="`不合格 ${stats.defective} 件`" />
        <RingGauge v-if="task.ratio !== null" :title="task.label" :ratio="task.ratio" :detail="task.text" />
        <RingGauge v-else title="累计检测" :ratio="stats.total ? 1 : 0" :reading="String(stats.total)" :detail="controller.state.settings.mode" tone="neutral" />
      </div>
    </section>

    <section class="section-block">
      <h2>不合格分类</h2>
      <div class="ring-row category-rings">
        <RingGauge v-for="[name, title] in categories" :key="name" :title="title" tone="accent" :ratio="ofDefective(name)" :detail="`${stats[name] || 0} 次 · 占不合格`" />
      </div>
    </section>

    <details class="section-block inference-details"><summary>推理详情</summary><p class="muted">{{ controller.historical ? '上次检测数据' : '最近一次检测数据' }}</p>
      <dl class="diagnostics"><div><dt>划痕概率</dt><dd>{{ probability('scratch') }}</dd></div><div><dt>缺口概率</dt><dd>{{ probability('missing_hole') }}</dd></div><div><dt>划痕阈值</dt><dd>{{ controller.state.settings.scratch_threshold.toFixed(6) }}</dd></div><div><dt>缺口阈值</dt><dd>{{ controller.state.settings.missing_hole_threshold.toFixed(6) }}</dd></div><div><dt>总耗时</dt><dd>{{ ms(controller.result?.elapsed_ms) }}</dd></div><div><dt>定位耗时</dt><dd>{{ ms(controller.result?.timings?.locator_ms) }}</dd></div><div><dt>划痕耗时</dt><dd>{{ ms(controller.result?.timings?.scratch?.total_ms) }}</dd></div><div><dt>缺口耗时</dt><dd>{{ ms(controller.result?.timings?.missing_hole?.total_ms) }}</dd></div></dl>
      <p class="model-version">模型：{{ controller.result?.model_versions ? `${controller.result.model_versions.scratch} / ${controller.result.model_versions.missing_hole}` : '暂无检测数据' }}</p>
    </details>
  </div>
</template>
