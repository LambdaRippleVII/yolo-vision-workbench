<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { t } from '../locales'

const route = useRoute()
const router = useRouter()

const items = computed(() => [
  { name: 'projects', path: '/projects', label: t('nav.projects'), icon: '▤' },
  { name: 'models', path: '/models', label: t('nav.models'), icon: '◈' },
  { name: 'datasets', path: '/datasets', label: t('nav.datasets'), icon: '▦' },
  { name: 'tasks', path: '/tasks', label: t('nav.tasks'), icon: '☰' },
  { name: 'devices', path: '/devices', label: t('nav.devices'), icon: '⚙' },
  { name: 'settings', path: '/settings', label: t('nav.settings'), icon: '⚒' }
])

function go(path: string): void {
  void router.push(path)
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
      <span class="nav-icon" aria-hidden="true">{{ item.icon }}</span>
      <span class="nav-label">{{ item.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.side-nav.slim {
  width: 56px;
  padding-top: 6px;
}
.side-nav.slim .nav-label {
  font-size: 9px;
  line-height: 1.15;
}
</style>
