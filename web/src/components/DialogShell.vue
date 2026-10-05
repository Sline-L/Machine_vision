<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
const props = defineProps({ title: String, wide: Boolean, busy: Boolean, restoreSelector: String })
const emit = defineEmits(['close'])
const panel = ref(null)
let returnFocus
onMounted(() => { returnFocus = document.activeElement; panel.value.focus() })
onBeforeUnmount(() => {
  nextTick(() => {
    if (props.restoreSelector) document.querySelector(props.restoreSelector)?.focus()
    else if (returnFocus?.isConnected) returnFocus.focus()
  })
})
function trapFocus(event) {
  if (event.key !== 'Tab') return
  const items = [...panel.value.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), [tabindex="0"]')]
  const first = items[0], last = items.at(-1)
  if (!first) { event.preventDefault(); return }
  if (event.shiftKey && [panel.value, first].includes(document.activeElement)) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && [panel.value, last].includes(document.activeElement)) { event.preventDefault(); first.focus() }
}
</script>

<template>
  <Teleport to="body">
    <div class="modal" @click.self="!busy && emit('close')" @keydown.esc.prevent="!busy && emit('close')" @keydown="trapFocus">
      <section ref="panel" :class="['dialog', { wide }]" role="dialog" aria-modal="true" aria-labelledby="dialog-title" tabindex="-1">
        <header class="dialog-heading"><h2 id="dialog-title">{{ title }}</h2><button class="button" :disabled="busy" @click="emit('close')">关闭</button></header>
        <slot />
      </section>
    </div>
  </Teleport>
</template>
