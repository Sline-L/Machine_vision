<script setup>
defineProps({ controller: Object })
</script>
<template>
  <dl class="stats-strip" aria-label="累计检测统计">
    <div><dt>累计检测</dt><dd>{{ controller.state.stats.total }}</dd></div>
    <div class="good"><dt>合格</dt><dd>{{ controller.state.stats.good }}</dd></div>
    <div class="defective"><dt>不合格</dt><dd>{{ controller.state.stats.defective }}</dd></div>
    <div><dt>合格率</dt><dd>{{ controller.goodRate }}</dd></div>
  </dl>
</template>
