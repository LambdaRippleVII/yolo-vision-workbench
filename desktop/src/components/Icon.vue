<script setup lang="ts">
/**
 * 线性图标集（统一 1.75 描边 / 24 网格）。
 * 禁用 emoji 与混合风格图标；新增图标请保持圆头圆角、视觉重量一致。
 */
const props = defineProps<{
  name:
    | 'workbench'
    | 'projects'
    | 'models'
    | 'datasets'
    | 'tasks'
    | 'devices'
    | 'settings'
    | 'image'
    | 'video'
    | 'camera'
    | 'play'
    | 'sun'
    | 'moon'
    | 'restart'
    | 'pin'
  size?: number
}>()

const s = props.size ?? 18
</script>

<template>
  <!-- 根据图标名称渲染共享的线框 SVG 图形。 -->
  <svg
    class="icon"
    :width="s"
    :height="s"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.75"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <!-- 工作台或网格图标 -->
    <template v-if="name === 'workbench' || name === 'image'">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </template>
    <template v-else-if="name === 'projects'">
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </template>
    <template v-else-if="name === 'models'">
      <path d="M12 3 20 7.5v9L12 21 4 16.5v-9z" />
      <path d="M12 12 20 7.5M12 12v9M12 12 4 7.5" />
    </template>
    <template v-else-if="name === 'datasets'">
      <ellipse cx="12" cy="6" rx="7" ry="3" />
      <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
      <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
    </template>
    <template v-else-if="name === 'tasks' || name === 'video'">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M10 9.5 15 12l-5 2.5z" />
    </template>
    <template v-else-if="name === 'devices' || name === 'camera'">
      <path d="M4 8h3l2-2h6l2 2h3v10H4z" />
      <circle cx="12" cy="13" r="3.5" />
    </template>
    <template v-else-if="name === 'settings'">
      <circle cx="12" cy="12" r="3" />
      <path
        d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6"
      />
    </template>
    <template v-else-if="name === 'play'">
      <circle cx="12" cy="12" r="8" />
      <path d="M10 9.2 15.2 12 10 14.8z" />
    </template>
    <template v-else-if="name === 'sun'">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.8v2M12 19.2v2M2.8 12h2M19.2 12h2M5.5 5.5l1.4 1.4M17.1 17.1l1.4 1.4M18.5 5.5l-1.4 1.4M6.9 17.1l-1.4 1.4" />
    </template>
    <template v-else-if="name === 'moon'">
      <path d="M20 13.5A8 8 0 0 1 10.5 4 7.2 7.2 0 1 0 20 13.5z" />
    </template>
    <template v-else-if="name === 'restart'">
      <path d="M20 12a8 8 0 1 1-2.6-5.9" />
      <path d="M20 4v4.2h-4.2" />
    </template>
    <template v-else-if="name === 'pin'">
      <path d="m16 3 5 5-4 1-3 3-1 4-2-2-6 6-.7-.7 6-6-2-2 4-1 3-3z" />
    </template>
  </svg>
</template>

<style scoped>
.icon {
  display: block;
  flex-shrink: 0;
}
</style>
