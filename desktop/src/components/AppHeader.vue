<script setup lang="ts">
import { computed } from 'vue'
import { t } from '../locales'

export interface BackendStatusInfo {
  status: string
  restarts: number
  port: number
  host: string
}

const props = defineProps<{
  backend: BackendStatusInfo
  wsState: string
  pingMs: number | null
  theme: 'light' | 'dark'
  projectLabel?: string
  backendMessage?: string
}>()

const emit = defineEmits<{
  restart: []
  toggleTheme: []
}>()

const backendLabel = computed(() => {
  const map: Record<string, string> = {
    ready: t('backend.ready'),
    starting: t('backend.starting'),
    restarting: t('backend.restarting'),
    unhealthy: t('backend.unhealthy'),
    failed: t('backend.failed'),
    stopped: t('backend.stopped'),
    reused: t('backend.reused'),
    unknown: t('backend.unknown')
  }
  return map[props.backend.status] ?? t('backend.unknown')
})

const backendChipClass = computed(() => {
  switch (props.backend.status) {
    case 'ready':
      return 'ok'
    case 'starting':
    case 'restarting':
    case 'unhealthy':
      return 'warn'
    case 'failed':
      return 'err'
    default:
      return ''
  }
})

const wsLabel = computed(() => {
  if (props.wsState === 'connected') return t('ws.connected')
  if (props.wsState === 'connecting') return t('ws.connecting')
  return t('ws.disconnected')
})
</script>

<template>
  <header class="shell-header">
    <div class="brand">
      <div class="brand-title">{{ t('app.name') }}</div>
      <div class="brand-tag">{{ t('app.tagline') }}</div>
    </div>

    <div class="header-sep" />
    <slot name="modes" />
    <div class="header-sep" />
    <div class="header-project">
      <span class="proj-label">{{ t('top.currentProject') }}</span>
      <strong>{{ projectLabel || t('top.noProject') }}</strong>
    </div>

    <div class="header-spacer" />

    <div class="header-status">
      <span class="status-chip" :class="backendChipClass" :title="backendMessage">
        <span class="status-dot" />
        {{ t('backend.label') }}：{{ backendLabel }}
        <template v-if="backend.port"> :{{ backend.port }}</template>
      </span>
      <span class="status-chip" :class="wsState === 'connected' ? 'ok' : 'err'">
        <span class="status-dot" />
        {{ t('ws.label') }}：{{ wsLabel }}
      </span>
      <span v-if="pingMs !== null" class="status-chip num">{{ pingMs }} ms</span>
    </div>

    <button
      class="icon-btn"
      :title="t('top.switchTheme')"
      type="button"
      @click="emit('toggleTheme')"
    >
      {{ theme === 'dark' ? '☾' : '☀' }}
    </button>

    <button class="ghost" type="button" @click="emit('restart')">
      {{ t('backend.restart') }}
    </button>
  </header>
</template>
