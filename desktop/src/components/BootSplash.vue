<script setup lang="ts">
import { computed } from 'vue'
import { t } from '../locales'
import BrandMark from './BrandMark.vue'

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
  <!-- 启动品牌动画与当前启动阶段的进度提示。 -->
  <Transition name="boot-fade">
    <div v-if="visible" class="boot-splash" role="status" aria-live="polite">
      <div class="boot-card">
        <BrandMark :size="76" animate />
        <h1 class="boot-title">{{ t('app.name') }}</h1>
        <p class="sub">{{ t('app.tagline') }}</p>

        <div class="progress"><div class="bar" /></div>
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
  background: var(--bg-app);
}

.boot-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
  padding: 32px 44px;
  min-width: 300px;
}

.boot-card :deep(.brand-mark) {
  margin-bottom: 10px;
}

.boot-title {
  display: block;
  margin: 0;
  font-size: 20px;
  font-weight: 680;
  letter-spacing: var(--tracking-tight);
}

.sub {
  margin: 0;
  color: var(--text-muted);
  font-size: var(--text-sm);
}

/* 进度条：一条 2px 的细线，不喧宾夺主 */
.progress {
  width: 200px;
  height: 2px;
  margin-top: 22px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--border) 85%, transparent);
  overflow: hidden;
}

.progress .bar {
  height: 100%;
  width: 38%;
  border-radius: 999px;
  background: var(--accent);
  animation: boot-slide 1.25s var(--ease-inout, cubic-bezier(0.65, 0, 0.35, 1)) infinite;
}

.status {
  margin: 12px 0 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.hint {
  margin: 2px 0 0;
  font-size: var(--text-xs);
  color: var(--text-muted);
}

@keyframes boot-slide {
  0% {
    transform: translateX(-110%);
  }
  100% {
    transform: translateX(290%);
  }
}

.boot-fade-enter-active,
.boot-fade-leave-active {
  transition:
    opacity 0.28s var(--ease),
    transform 0.28s var(--ease);
}
.boot-fade-enter-from,
.boot-fade-leave-to {
  opacity: 0;
  transform: scale(1.01);
}
</style>
