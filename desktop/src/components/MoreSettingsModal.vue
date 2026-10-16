<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  conf: number
  maxSide: number
  labelTemplate: string
}>()

const emit = defineEmits<{
  'update:visible': [boolean]
  apply: [payload: { conf: number; maxSide: number; labelTemplate: string }]
}>()

const conf = ref(props.conf)
const maxSide = ref(props.maxSide)
const labelTemplate = ref(props.labelTemplate)

watch(
  () => props.visible,
  (v) => {
    if (v) {
      conf.value = props.conf
      maxSide.value = props.maxSide
      labelTemplate.value = props.labelTemplate
    }
  },
  { immediate: true }
)

function apply(): void {
  emit('apply', {
    conf: conf.value,
    maxSide: Math.max(320, Math.min(4096, Math.round(maxSide.value))),
    labelTemplate: labelTemplate.value || '{id}:{class}'
  })
  emit('update:visible', false)
}
</script>

<template>
  <!-- 图片检测的高级参数面板，集中编辑阈值和结果显示选项。 -->
  <div v-if="visible" class="mask" @click.self="emit('update:visible', false)">
    <div class="dialog">
      <h3 class="title">更多配置</h3>
      <div class="grid">
        <label>置信度阈值</label>
        <input v-model.number="conf" type="number" min="0" max="1" step="0.05" />
        <label>推理最长边（px）</label>
        <input v-model.number="maxSide" type="number" min="320" max="4096" step="32" />
        <label>标签模板</label>
        <input v-model="labelTemplate" type="text" />
      </div>
      <p class="hint">
        最长边用于推理前缩放大图，加快速度；显示与导出仍用原始分辨率叠加框坐标（按缩放换算）。
      </p>
      <div class="actions">
        <button type="button" @click="emit('update:visible', false)">取消</button>
        <button type="button" class="primary" @click="apply">应用</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  background: rgba(20, 28, 40, 0.35);
  display: grid;
  place-items: center;
  z-index: 1100;
}
.dialog {
  width: min(420px, 92vw);
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 18px;
  box-shadow: var(--shadow-md);
}
.title {
  margin: 0 0 12px;
  font-size: var(--text-lg);
}
.grid {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 10px;
  align-items: center;
  font-size: var(--text-sm);
}
.grid input {
  height: 30px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0 8px;
  background: var(--bg-inset);
  color: var(--text-primary);
}
.hint {
  margin: 12px 0;
  color: var(--text-muted);
  font-size: var(--text-xs);
  line-height: 1.5;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.dialog,
.style-dialog {
  animation: dialog-pop 260ms var(--spring) both;
}
@keyframes dialog-pop {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
</style>
