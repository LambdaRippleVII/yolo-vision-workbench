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
  withViewTransition(() => router.push(path))
}
</script>

<template>
  <!-- 左侧主导航：在检测工作区和资源管理页面之间切换。 -->
  <nav class="side-nav" :aria-label="t('app.name')">
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
