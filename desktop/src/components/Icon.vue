<script setup lang="ts">
/**
 * Stroke icon set (consistent 1.75px), Operate UI.
 * Avoids unicode/emoji glyphs per craft floor.
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
  size?: number
}>()

const s = props.size ?? 18
</script>

<template>
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
    <!-- workbench / grid -->
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
  </svg>
</template>

<style scoped>
.icon {
  display: block;
  flex-shrink: 0;
}
</style>
