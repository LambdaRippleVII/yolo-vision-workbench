<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ClassPickerModal from './ClassPickerModal.vue'

export interface ModelItem {
  model_id: string
  name: string
  loaded: boolean
  class_list?: Array<{ class_id: number; class_name: string; display_name: string }>
}

const props = defineProps<{
  models: ModelItem[]
  selected: string[]
  compact?: boolean
}>()

const emit = defineEmits<{
  'update:selected': [string[]]
  toggleModel: [modelId: string, checked: boolean]
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

defineExpose({ classFilter })
</script>

<template>
  <div class="model-picker" :class="{ compact }">
    <div class="list">
      <label v-for="m in models" :key="m.model_id" class="row">
        <input
          type="checkbox"
          :checked="selected.includes(m.model_id)"
          @change="onToggle(m.model_id, ($event.target as HTMLInputElement).checked)"
        />
        <span class="name">{{ m.name }}</span>
        <span class="badge" :class="m.loaded ? 'ok' : ''">
          {{ m.loaded ? '已加载' : '未加载' }}
        </span>
      </label>
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
  gap: 8px;
  align-items: center;
  font-size: var(--text-sm);
  min-width: 0;
}
.name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
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
