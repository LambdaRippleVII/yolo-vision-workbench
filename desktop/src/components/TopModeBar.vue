<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Icon from './Icon.vue'
import { t } from '../locales'

const route = useRoute()
const router = useRouter()

const inferenceItems = computed(() => [
  { path: '/image', label: t('nav.imageDetect'), icon: 'image' as const },
  { path: '/video-editor', label: t('nav.videoEditor'), icon: 'video' as const },
  { path: '/camera', label: t('nav.camera'), icon: 'camera' as const }
])

function go(path: string): void {
  void router.push(path)
}
</script>

<template>
  <div class="top-modes">
    <button
      v-for="item in inferenceItems"
      :key="item.path"
      type="button"
      class="mode-btn"
      :class="{ active: route.path.startsWith(item.path) }"
      @click="go(item.path)"
    >
      <Icon :name="item.icon" :size="16" />
      {{ item.label }}
    </button>
  </div>
</template>

<style scoped>
.top-modes {
  display: flex;
  align-items: center;
  gap: 4px;
}
.mode-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-md);
}
.mode-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.mode-btn.active {
  background: var(--accent-soft);
  color: var(--accent);
  border-color: color-mix(in srgb, var(--accent) 22%, transparent);
  font-weight: 550;
}
</style>
