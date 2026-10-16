<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { withViewTransition } from '../router'
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
  withViewTransition(() => router.push(path))
}
</script>

<template>
  <!-- 检测工作区模式栏，用于切换图片、视频和摄像头任务。 -->
  <div class="top-modes" role="tablist" :aria-label="t('nav.workbench')">
    <button
      v-for="item in inferenceItems"
      :key="item.path"
      type="button"
      role="tab"
      class="mode-btn"
      :class="{ active: route.path.startsWith(item.path) }"
      :aria-selected="route.path.startsWith(item.path)"
      @click="go(item.path)"
    >
      <Icon :name="item.icon" :size="15" />
      {{ item.label }}
    </button>
  </div>
</template>
