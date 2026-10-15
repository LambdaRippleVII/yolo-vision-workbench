<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { withViewTransition } from '../router'
import Icon from './Icon.vue'
import { t } from '../locales'

const route = useRoute()
const router = useRouter()

const items = computed(() => [
  { name: 'projects', path: '/projects', label: t('nav.projects'), icon: 'projects' as const },
  { name: 'models', path: '/models', label: t('nav.models'), icon: 'models' as const },
  { name: 'datasets', path: '/datasets', label: t('nav.datasets'), icon: 'datasets' as const },
  { name: 'tasks', path: '/tasks', label: t('nav.tasks'), icon: 'tasks' as const },
  { name: 'devices', path: '/devices', label: t('nav.devices'), icon: 'devices' as const },
  { name: 'settings', path: '/settings', label: t('nav.settings'), icon: 'settings' as const }
])

function go(path: string): void {
  withViewTransition(() => { void router.push(path) })
}
</script>

<template>
  <nav class="side-nav slim" :aria-label="t('app.name')">
    <button
      v-for="item in items"
      :key="item.name"
      type="button"
      class="nav-item"
      :class="{ active: route.path.startsWith(item.path) }"
      :title="item.label"
      @click="go(item.path)"
    >
      <Icon :name="item.icon" :size="18" />
      <span class="nav-label">{{ item.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.side-nav.slim {
  width: 56px;
  padding-top: 8px;
  gap: 2px;
}
.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 10px 4px 8px;
  border: none;
  border-left: 3px solid transparent;
  border-radius: 0;
  background: transparent;
  color: var(--text-secondary);
}
.nav-item:hover {
  background: var(--bg-hover);
  border-color: transparent;
  color: var(--text-primary);
}
.nav-item.active {
  background: var(--bg-active);
  border-left-color: var(--accent);
  color: var(--accent);
}
.nav-label {
  font-size: 9px;
  line-height: 1.2;
  letter-spacing: 0;
}
</style>
