<script setup lang="ts">
defineProps<{
  icon?: string
  title: string
  description?: string
  actionLabel?: string
}>()

const emit = defineEmits<{ action: [] }>()
</script>

<template>
  <div class="empty-state">
    <div class="empty-icon" aria-hidden="true">{{ icon || '◎' }}</div>
    <h3 class="empty-title">{{ title }}</h3>
    <p v-if="description" class="empty-desc">{{ description }}</p>
    <button v-if="actionLabel" type="button" class="primary" @click="emit('action')">
      {{ actionLabel }}
    </button>
    <slot />
  </div>
</template>
