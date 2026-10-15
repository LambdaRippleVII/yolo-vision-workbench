<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ClassPickerModal from './ClassPickerModal.vue'

export interface ModelItem {
  model_id: string
  name: string
  loaded: boolean
  weights_available?: boolean
  downloadable?: boolean
  runtime_available?: boolean
  class_list?: Array<{ class_id: number; class_name: string; display_name: string }>
}

const props = defineProps<{
  models: ModelItem[]
  selected: string[]
  compact?: boolean
  downloadingModelId?: string
}>()

const emit = defineEmits<{
  'update:selected': [string[]]
  toggleModel: [modelId: string, checked: boolean]
  download: [modelId: string]
}>()

const classFilter = ref<Record<string, string[]>>({})
const classModalModel = ref('')

const activeModels = computed(() => props.models.filter((m) => props.selected.includes(m.model_id)))
const classModalModelItem = computed(
  () => props.models.find((m) => m.model_id === classModalModel.value) || null
)

watch(
  () => props.models,
  () => {
    for (const m of props.models) {
      if (!classFilter.value[m.model_id] && m.class_list?.length) {
        classFilter.value = {
          ...classFilter.value,
          [m.model_id]: m.class_list.map((c) => c.class_name)
        }
      }
    }
  },
  { immediate: true, deep: true }
)

function onToggle(modelId: string, checked: boolean): void {
  const set = new Set(props.selected)
  if (checked) set.add(modelId)
  else set.delete(modelId)
  emit('update:selected', [...set])
  emit('toggleModel', modelId, checked)
}

function onClassUpdate(modelId: string, list: string[]): void {
  classFilter.value = { ...classFilter.value, [modelId]: list }
}

function statusLabel(model: ModelItem): string {
  if (model.runtime_available === false) return '缺少推理组件'
  if (model.weights_available === false) return model.downloadable ? '未下载' : '缺少权重'
  return model.loaded ? '已加载' : '未加载'
}

defineExpose({ classFilter })
</script>

<template>
  <div class="model-picker" :class="{ compact }">
    <div class="list">
      <div v-for="m in models" :key="m.model_id" class="row">
        <label class="model-toggle">
          <input
            type="checkbox"
            :checked="selected.includes(m.model_id)"
            @change="onToggle(m.model_id, ($event.target as HTMLInputElement).checked)"
          />
          <span class="name">{{ m.name }}</span>
        </label>
        <div class="status-tools">
          <span
            class="badge"
            :class="{
              ok: m.loaded && m.runtime_available !== false && m.weights_available !== false,
              missing: m.runtime_available === false || m.weights_available === false
            }"
          >{{ statusLabel(m) }}</span>
          <button
            v-if="m.weights_available === false && m.downloadable && m.runtime_available !== false"
            type="button"
            class="ghost mini download-btn"
            :disabled="Boolean(downloadingModelId)"
            @click.stop.prevent="emit('download', m.model_id)"
          >
            {{ downloadingModelId === m.model_id ? '下载中…' : '下载' }}
          </button>
        </div>
      </div>
      <div v-if="!models.length" class="muted">暂无模型</div>
    </div>

    <div v-for="m in activeModels" :key="m.model_id" class="cls-row">
      <button type="button" class="ghost mini" @click="classModalModel = m.model_id">
        {{ m.name }} 类别 {{ (classFilter[m.model_id] ?? []).length }}/{{ (m.class_list || []).length }}
      </button>
    </div>

    <ClassPickerModal
      :visible="!!classModalModelItem"
      :title="`${classModalModelItem?.name || ''} · 类别选择`"
      :classes="classModalModelItem?.class_list || []"
      :selected="classFilter[classModalModel] ?? []"
      @update:visible="(v) => { if (!v) classModalModel = '' }"
      @update:selected="(list) => onClassUpdate(classModalModel, list)"
    />
  </div>
</template>

<style scoped>
.model-picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: auto;
  min-height: 0;
}
.row {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: var(--text-sm);
  min-width: 0;
}
.model-toggle {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0;
  flex: 1;
}
.name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.status-tools {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 0 0 auto;
}
.badge.missing {
  color: var(--warning, #a76500);
  background: var(--warning-soft, #fff3d6);
}
.download-btn {
  padding: 2px 5px;
}
.cls-row {
  overflow: hidden;
}
.mini {
  padding: 2px 6px;
  font-size: 11px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.muted {
  color: var(--text-muted);
  font-size: var(--text-sm);
}
</style>
