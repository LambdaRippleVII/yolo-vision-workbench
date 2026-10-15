<script setup lang="ts">
import { computed, ref, watch } from 'vue'

export interface ClassOption {
  class_id: number
  class_name: string
  display_name: string
}

const props = defineProps<{
  visible: boolean
  title: string
  classes: ClassOption[]
  selected: string[]
}>()

const emit = defineEmits<{
  'update:visible': [boolean]
  'update:selected': [string[]]
  confirm: [string[]]
}>()

const keyword = ref('')
const localSelected = ref<string[]>([])

watch(
  () => props.visible,
  (v) => {
    if (v) {
      localSelected.value = [...props.selected]
      keyword.value = ''
    }
  },
  { immediate: true }
)

const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return props.classes
  return props.classes.filter(
    (c) =>
      c.class_name.toLowerCase().includes(k) ||
      (c.display_name || '').toLowerCase().includes(k) ||
      (c.display_name || '').includes(keyword.value.trim())
  )
})

function toggle(name: string, checked: boolean): void {
  const set = new Set(localSelected.value)
  if (checked) set.add(name)
  else set.delete(name)
  localSelected.value = [...set]
}

function selectFiltered(): void {
  const set = new Set(localSelected.value)
  for (const c of filtered.value) set.add(c.class_name)
  localSelected.value = [...set]
}

function clearFiltered(): void {
  const drop = new Set(filtered.value.map((c) => c.class_name))
  localSelected.value = localSelected.value.filter((x) => !drop.has(x))
}

function selectAll(): void {
  localSelected.value = props.classes.map((c) => c.class_name)
}

function clearAll(): void {
  localSelected.value = []
}

function confirm(): void {
  emit('update:selected', localSelected.value)
  emit('confirm', localSelected.value)
  emit('update:visible', false)
}
</script>

<template>
  <div v-if="visible" class="mask" @click.self="emit('update:visible', false)">
    <div class="dialog">
      <div class="head">
        <h3 class="title">{{ title }}</h3>
        <span class="cnt">{{ localSelected.length }} / {{ classes.length }}</span>
      </div>
      <div class="toolbar">
        <input v-model="keyword" class="search" :placeholder="'搜索类别…'" />
        <button type="button" class="ghost mini" @click="selectFiltered">全选筛选</button>
        <button type="button" class="ghost mini" @click="clearFiltered">清空筛选</button>
        <button type="button" class="ghost mini" @click="selectAll">全选</button>
        <button type="button" class="ghost mini" @click="clearAll">清空</button>
      </div>
      <div class="list">
        <label v-for="c in filtered" :key="c.class_name" class="row">
          <input
            type="checkbox"
            :checked="localSelected.includes(c.class_name)"
            @change="toggle(c.class_name, ($event.target as HTMLInputElement).checked)"
          />
          <span class="dname">{{ c.display_name || c.class_name }}</span>
          <span class="cname num">{{ c.class_name }}</span>
        </label>
        <div v-if="!filtered.length" class="empty">无匹配类别</div>
      </div>
      <div class="actions">
        <button type="button" @click="emit('update:visible', false)">取消</button>
        <button type="button" class="primary" @click="confirm">确定</button>
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
  width: min(480px, 92vw);
  max-height: 70vh;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: var(--shadow-md);
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  margin: 0;
  font-size: var(--text-lg);
}
.cnt {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
.toolbar {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.search {
  flex: 1;
  min-width: 140px;
  height: 30px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0 10px;
  background: var(--bg-inset);
  color: var(--text-primary);
  font-size: var(--text-sm);
}
.mini {
  padding: 2px 8px;
  font-size: 11px;
}
.list {
  overflow: auto;
  min-height: 220px;
  max-height: 360px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 8px;
}
.row {
  display: grid;
  grid-template-columns: 18px 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 6px 4px;
  border-bottom: 1px solid color-mix(in srgb, var(--border) 40%, transparent);
  font-size: var(--text-sm);
}
.dname {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cname {
  color: var(--text-muted);
  font-size: 11px;
}
.empty {
  color: var(--text-muted);
  text-align: center;
  padding: 24px 0;
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
