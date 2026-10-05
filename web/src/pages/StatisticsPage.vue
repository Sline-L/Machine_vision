<script setup>
import StatsStrip from '../components/StatsStrip.vue'
const props = defineProps({ controller: Object })
defineEmits(['reset'])
const categories = [['scratch','划痕'],['missing_hole','缺齿 / 缺口'],['combined','同时命中']]
function share(name) {
  const stats = props.controller.state.stats
  return stats.defective ? Math.max(0, Math.min(100, (stats[name] || 0) / stats.defective * 100)) : 0
}
function probability(name) {
  const values = props.controller.result?.observations?.map(item => item.specialists?.[name]?.probability).filter(Number.isFinite) || []
  return values.length ? `${(Math.max(...values) * 100).toFixed(2)}%` : '—'
}
const ms = value => Number.isFinite(value) ? `${value.toFixed(1)} ms` : '—'
</script>
<template>
  <div class="scroll-page statistics-page">
    <header class="page-heading"><h1>检测统计</h1><button class="button" :disabled="!controller.canControl" @click="$emit('reset')">清空统计</button></header>
    <StatsStrip :controller="controller" />
    <section class="section-block">
      <h2>不合格分类</h2><p class="muted">占累计不合格判定的比例</p>
      <div class="category-rings">
        <figure v-for="[name, title] in categories" :key="name" class="category-ring">
          <div class="ring-reading">
            <svg viewBox="0 0 120 120" role="img" :aria-label="`${title} ${controller.state.stats[name] || 0} 次，占不合格判定 ${controller.state.stats.defective ? share(name).toFixed(1) + '%' : '暂无数据'}`">
              <circle class="ring-track" cx="60" cy="60" r="50" />
              <circle class="ring-progress" cx="60" cy="60" r="50" pathLength="100" :stroke-dasharray="`${share(name)} 100`" transform="rotate(-90 60 60)" />
            </svg>
            <strong>{{ controller.state.stats.defective ? share(name).toFixed(1) + '%' : '—' }}</strong>
          </div>
          <figcaption><span>{{ title }}</span><strong>{{ controller.state.stats[name] || 0 }} <small>次</small></strong></figcaption>
        </figure>
      </div>
    </section>
    <details class="section-block inference-details"><summary>推理详情</summary><p class="muted">{{ controller.historical ? '上次检测数据' : '最近一次检测数据' }}</p>
      <dl class="diagnostics"><div><dt>划痕概率</dt><dd>{{ probability('scratch') }}</dd></div><div><dt>缺口概率</dt><dd>{{ probability('missing_hole') }}</dd></div><div><dt>划痕阈值</dt><dd>{{ controller.state.settings.scratch_threshold.toFixed(6) }}</dd></div><div><dt>缺口阈值</dt><dd>{{ controller.state.settings.missing_hole_threshold.toFixed(6) }}</dd></div><div><dt>总耗时</dt><dd>{{ ms(controller.result?.elapsed_ms) }}</dd></div><div><dt>定位耗时</dt><dd>{{ ms(controller.result?.timings?.locator_ms) }}</dd></div><div><dt>划痕耗时</dt><dd>{{ ms(controller.result?.timings?.scratch?.total_ms) }}</dd></div><div><dt>缺口耗时</dt><dd>{{ ms(controller.result?.timings?.missing_hole?.total_ms) }}</dd></div></dl>
      <p class="model-version">模型：{{ controller.result?.model_versions ? `${controller.result.model_versions.scratch} / ${controller.result.model_versions.missing_hole}` : '暂无检测数据' }}</p>
    </details>
  </div>
</template>
