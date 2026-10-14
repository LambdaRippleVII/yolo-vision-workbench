<script setup lang="ts">
import { computed } from 'vue'
import { t } from '../locales'

const props = defineProps<{
  status: string
  message?: string
  progressHint?: string
}>()

const visible = computed(() => {
  return (
    props.status === 'starting' ||
    props.status === 'restarting' ||
    props.status === 'unknown' ||
    props.status === 'stopped'
  )
})

const label = computed(() => {
  if (props.status === 'restarting') return t('splash.restarting')
  return t('splash.starting')
})
</script>

<template>
  <Transition name="boot-fade">
    <div v-if="visible" class="boot-splash" role="status" aria-live="polite">
      <div class="boot-card">
        <div class="logo-mark">
          <span class="ring" />
          <span class="core">Y</span>
        </div>
        <h1 class="brand">{{ t('app.name') }}</h1>
        <p class="sub">{{ t('app.tagline') }}</p>

        <div class="progress">
          <div class="bar" />
        </div>
        <p class="status">{{ message || label }}</p>
        <p class="hint">{{ t('splash.hint') }}</p>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.boot-splash {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: grid;
  place-items: center;
  background:
    radial-gradient(1200px 600px at 50% -10%, color-mix(in srgb, var(--accent) 12%, transparent), transparent),
    var(--bg-app);
}

.boot-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  text-align: center;
  padding: 36px 48px;
  min-width: 320px;
}

.logo-mark {
  position: relative;
  width: 72px;
  height: 72px;
  display: grid;
  place-items: center;
  margin-bottom: 8px;
}

.logo-mark .ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid color-mix(in srgb, var(--accent) 25%, transparent);
  border-top-color: var(--accent);
  animation: spin 1.1s linear infinite;
}

.logo-mark .core {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: var(--accent);
  color: #fff;
  font-weight: 700;
  font-size: 22px;
  display: grid;
  place-items: center;
  box-shadow: 0 8px 24px color-mix(in srgb, var(--accent) 35%, transparent);
}

.brand {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: 0.2px;
}

.sub {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
}

.progress {
  width: 220px;
  height: 3px;
  margin-top: 18px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--border) 80%, transparent);
  overflow: hidden;
}

.progress .bar {
  height: 100%;
  width: 40%;
  border-radius: 999px;
  background: var(--accent);
  animation: slide 1.2s ease-in-out infinite;
}

.status {
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.hint {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--text-muted);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes slide {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(280%);
  }
}

.boot-fade-enter-active,
.boot-fade-leave-active {
  transition: opacity 0.35s var(--ease), transform 0.35s var(--ease);
}
.boot-fade-enter-from,
.boot-fade-leave-to {
  opacity: 0;
  transform: scale(1.02);
}
</style>
