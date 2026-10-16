<script setup lang="ts">
import { computed } from 'vue'
import Icon from './Icon.vue'

const props = defineProps<{
  icon?: string
  title: string
  description?: string
  actionLabel?: string
}>()

const emit = defineEmits<{ action: [] }>()
const iconName = computed(() => {
  const icons: Record<string, 'datasets' | 'devices' | 'image' | 'models' | 'play' | 'projects' | 'tasks' | 'video'> = {
    '▦': 'datasets',
    '⬡': 'devices',
    '◈': 'models',
    '▣': 'image',
    '▤': 'projects',
    '▶': 'play'
  }
  return icons[props.icon || ''] || 'workbench'
})
</script>

<template>
  <!-- 空状态插槽：解释当前工作区状态，并提供可选的下一步操作。 -->
  <div class="empty-state">
    <div class="empty-icon" aria-hidden="true"><Icon :name="iconName" :size="22" /></div>
    <h3 class="empty-title">{{ title }}</h3>
    <p v-if="description" class="empty-desc">{{ description }}</p>
    <button v-if="actionLabel" type="button" class="primary" @click="emit('action')">
      {{ actionLabel }}
    </button>
    <slot />
  </div>
</template>
