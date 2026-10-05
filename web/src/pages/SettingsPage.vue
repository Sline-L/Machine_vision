<script setup>
import { computed, reactive, ref, watch } from 'vue'
const props = defineProps({ controller: Object })
const emit = defineEmits(['dirty'])
const fields = ['mode','inference_profile','target_quantity','duration_minutes','inference_interval','locator_confidence','scratch_threshold','missing_hole_threshold','camera_index','serial_port','serial_baudrate','stream_fps','stream_quality']
const pick = source => Object.fromEntries(fields.map(key => [key, source[key]]))
const draft = reactive(pick(props.controller.state.settings))
const saved = ref(JSON.stringify(draft))
const feedback = ref('')
let restoring = false
const dirty = computed(() => JSON.stringify(draft) !== saved.value)
watch(dirty, value => { if (value) feedback.value = ''; emit('dirty', value) })
watch(() => draft.inference_profile, (profile, previous) => {
  if (restoring || profile === previous) return
  if (profile === 'FULL') draft.inference_interval = .10
  if (profile === 'SPARSE') draft.inference_interval = .20
}, { flush: 'sync' })
async function save() {
  if (await props.controller.action('/settings', { ...draft })) {
    restore()
    feedback.value = '设置已保存'
  }
}
function restore() {
  restoring = true
  Object.assign(draft, pick(props.controller.state.settings))
  restoring = false
  saved.value = JSON.stringify(draft)
}
function defaults() {
  const values = props.controller.state.settings.model_default_thresholds
  if (values) { draft.scratch_threshold = values.scratch; draft.missing_hole_threshold = values.missing_hole }
}
</script>
<template>
  <form class="settings-page" @submit.prevent="save">
    <header class="page-heading"><h1>运行设置</h1><span>{{ dirty ? '有未保存修改' : '当前配置' }}</span></header>
    <div class="settings-scroll">
      <fieldset :disabled="!controller.canControl"><legend>运行任务</legend><div class="form-grid">
        <label>运行模式<select v-model="draft.mode"><option>自由模式</option><option>定量模式</option><option>定时模式</option><option v-if="draft.mode === '视频测试模式'">视频测试模式</option></select></label>
        <label>推理档位<select v-model="draft.inference_profile"><option value="FULL">完整检测（FULL）</option><option value="SPARSE">稀疏检测（SPARSE）</option><option value="SAFE_STOP">安全停止（SAFE_STOP）</option></select></label>
        <label v-if="draft.mode === '定量模式'">目标数量<input v-model.number="draft.target_quantity" type="number" min="1" required /></label>
        <label v-if="draft.mode === '定时模式'">运行时长（分钟）<input v-model.number="draft.duration_minutes" type="number" min="1" required /></label>
        <label>推理间隔（秒）<input v-model.number="draft.inference_interval" type="number" min="0.03" max="5" step="0.01" required /></label>
      </div></fieldset>
      <fieldset :disabled="!controller.canControl"><legend>判定参数</legend><div class="form-grid">
        <label>齿轮定位阈值<input v-model.number="draft.locator_confidence" type="number" min="0.01" max="0.99" step="0.01" required /></label>
        <label>划痕判定阈值<input v-model.number="draft.scratch_threshold" type="number" min="0.01" max="0.99" step="0.000001" required /></label>
        <label>缺齿 / 缺口阈值<input v-model.number="draft.missing_hole_threshold" type="number" min="0.01" max="0.99" step="0.000001" required /></label>
      </div><button type="button" class="button" @click="defaults">恢复模型默认阈值</button></fieldset>
      <fieldset :disabled="!controller.canControl"><legend>设备与画面</legend><div class="form-grid">
        <label>摄像头索引<input v-model.number="draft.camera_index" type="number" min="0" max="32" required /></label>
        <label>串口设备<input v-model="draft.serial_port" required /></label>
        <label>串口波特率<input v-model.number="draft.serial_baudrate" type="number" min="300" required /></label>
        <label>画面帧率<input v-model.number="draft.stream_fps" type="number" min="1" max="30" required /></label>
        <label>JPEG 质量<input v-model.number="draft.stream_quality" type="number" min="30" max="95" required /></label>
      </div></fieldset>
    </div>
    <footer class="settings-footer"><span v-if="!controller.canControl || feedback" role="status">{{ !controller.canControl ? '连接且拥有控制权后可保存' : feedback }}</span><button type="button" class="button" :disabled="controller.busy || !dirty" @click="restore">放弃修改</button><button class="button primary" :disabled="!controller.canControl || !dirty">{{ controller.operation === '/settings' ? '正在保存…' : '保存设置' }}</button></footer>
  </form>
</template>
