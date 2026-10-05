<script setup>
import { computed } from 'vue'
const props = defineProps({
  title: String,
  ratio: { type: Number, default: null },
  reading: String,
  detail: String,
  tone: { type: String, default: 'accent' },
})
const percent = computed(() => Number.isFinite(props.ratio) ? Math.max(0, Math.min(100, props.ratio * 100)) : 0)
const label = computed(() => props.reading ?? (Number.isFinite(props.ratio) ? `${percent.value.toFixed(1)}%` : '—'))
</script>

<template>
  <figure :class="['ring-gauge', tone]">
    <div class="ring-reading">
      <svg viewBox="0 0 120 120" role="img" :aria-label="`${title}：${label}${detail ? '，' + detail : ''}`">
        <circle class="ring-track" cx="60" cy="60" r="50" />
        <circle class="ring-progress" cx="60" cy="60" r="50" pathLength="100" :stroke-dasharray="`${percent} 100`" transform="rotate(-90 60 60)" />
      </svg>
      <strong>{{ label }}</strong>
    </div>
    <figcaption><span>{{ title }}</span><small v-if="detail">{{ detail }}</small></figcaption>
  </figure>
</template>
