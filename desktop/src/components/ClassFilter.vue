<script setup lang="ts">
import { computed } from 'vue'

export interface ClassOption {
  class_id: number
  class_name: string
  display_name: string
}

const props = defineProps<{
  classes: ClassOption[]
  modelId: string
  selected: string[]
}>()

const emit = defineEmits<{
  'update:selected': [string[]]
}>()

const allSelected = computed(
  () => props.classes.length > 0 && props.selected.length === props.classes.length
)

function toggle(name: string, checked: boolean): void {
  const set = new Set(props.selected)
  if (checked) set.add(name)
  else set.delete(name)
  emit('update:selected', [...set])
}

function selectAll(): void {
  emit('update:selected', props.classes.map((c) => c.class_name))
}

function clearAll(): void {
  emit('update:selected', [])
}
</script>

<template>
  <!-- 按模型展示类别清单，并将勾选变化回传给检测页。 -->
  <div class="class-filter">
    <div class="head">
      <span class="title">{{ modelId }} · 类别</span>
      <span class="ops">
        <button type="button" class="ghost mini" @click="selectAll">全选</button>
        <button type="button" class="ghost mini" @click="clearAll">清空</button>
      </span>
    </div>
    <div class="list">
      <label v-for="c in classes" :key="c.class_name" class="row">
        <input
          type="checkbox"
          :checked="selected.includes(c.class_name)"
          @change="toggle(c.class_name, ($event.target as HTMLInputElement).checked)"
        />
        <span class="name" :title="c.class_name">{{ c.display_name }}</span>
      </label>
      <div v-if="!classes.length" class="muted">加载模型后显示类别</div>
    </div>
  </div>
</template>

<style scoped>
.class-filter {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: 550;
}
.mini {
  padding: 2px 6px;
  font-size: 11px;
}
.list {
  max-height: 140px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.row {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: var(--text-sm);
}
.name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.muted {
  color: var(--text-muted);
  font-size: var(--text-xs);
}
</style>
