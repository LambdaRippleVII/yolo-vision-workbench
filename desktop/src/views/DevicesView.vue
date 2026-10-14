<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import EmptyState from '../components/EmptyState.vue'
import { t } from '../locales'

const health = ref<Record<string, unknown> | null>(null)

async function loadHealth(): Promise<void> {
  try {
    const res = await fetch('http://127.0.0.1:8765/health', { signal: AbortSignal.timeout(2000) })
    if (res.ok) health.value = (await res.json()) as Record<string, unknown>
    else health.value = null
  } catch {
    health.value = null
  }
}

let timer: number | undefined

onMounted(() => {
  void loadHealth()
  timer = window.setInterval(() => void loadHealth(), 5000)
})
onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">{{ t('devices.title') }}</h1>
      <div class="header-spacer" />
      <button type="button" class="ghost" @click="loadHealth">{{ t('action.refresh') }}</button>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h2 class="panel-title">{{ t('devices.backendInfo') }}</h2>
      </div>
      <div v-if="health" class="panel-body">
        <div class="field-row">
          <span class="field-label">{{ t('devices.version') }}</span>
          <span class="field-value num">{{ health.version }}</span>
        </div>
        <div class="field-row">
          <span class="field-label">{{ t('devices.pid') }}</span>
          <span class="field-value num">{{ health.pid }}</span>
        </div>
        <div class="field-row">
          <span class="field-label">{{ t('status.pending') }}</span>
          <span class="field-value">
            <span class="badge ok">{{ t('backend.ready') }}</span>
          </span>
        </div>
      </div>
      <EmptyState v-else icon="⬡" :title="t('devices.title')" :description="t('devices.empty')" />
    </div>
  </div>
</template>
