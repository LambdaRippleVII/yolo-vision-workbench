<script setup lang="ts">
import { computed, ref } from 'vue'
import { t } from '../locales'

export interface LogLine {
  ts: string
  level: string
  source: string
  message: string
}

const props = defineProps<{
  logs: LogLine[]
  expanded?: boolean
}>()

const emit = defineEmits<{
  'update:expanded': [boolean]
  clear: []
}>()

const tab = ref<'logs' | 'tasks' | 'devices'>('logs')

const levelLabel = computed(() => (level: string) => {
  const key = `log.level.${level}`
  return t(key) === key ? level : t(key)
})

const errorCount = computed(() => props.logs.filter((l) => l.level === 'ERROR' || l.level === 'CRITICAL').length)
const lastLine = computed(() => props.logs[0]?.message || t('console.empty'))
</script>

<template>
  <!-- 可折叠控制台：保留连接状态，并在展开后显示后端诊断日志。 -->
  <div class="console-root" :class="{ expanded }">
    <!-- 始终可见的窄状态栏 -->
    <div class="status-bar" @click="emit('update:expanded', !expanded)">
      <div class="tabs">
        <button type="button" class="tab" :class="{ active: tab === 'logs' }" @click.stop="tab = 'logs'">
          {{ t('console.logs') }}
          <span v-if="errorCount" class="err-badge">{{ errorCount }}</span>
        </button>
        <button type="button" class="tab" :class="{ active: tab === 'tasks' }" @click.stop="tab = 'tasks'">
          {{ t('console.tasks') }}
        </button>
        <button type="button" class="tab" :class="{ active: tab === 'devices' }" @click.stop="tab = 'devices'">
          {{ t('console.devices') }}
        </button>
      </div>
      <div class="last muted">{{ lastLine }}</div>
      <button type="button" class="ghost mini" @click.stop="emit('clear')">{{ t('console.clear') }}</button>
      <span class="chev">{{ expanded ? '▾' : '▴' }}</span>
    </div>

    <!-- 展开后的浮层日志面板 -->
    <div v-if="expanded" class="panel">
      <div class="body">
        <template v-if="tab === 'logs'">
          <div v-if="!props.logs.length" class="muted">{{ t('console.empty') }}</div>
          <div
            v-for="(line, i) in props.logs"
            :key="i"
            class="log-line"
            :class="line.level.toLowerCase()"
          >
            <span class="num">{{ line.ts }}</span>
            <span class="lvl">{{ levelLabel(line.level) }}</span>
            <span>{{ line.message }}</span>
          </div>
        </template>
        <template v-else-if="tab === 'tasks'">
          <div class="muted">{{ t('tasks.empty') }}</div>
        </template>
        <template v-else>
          <div class="muted">{{ t('devices.empty') }}</div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.console-root {
  position: relative;
  z-index: 20;
  flex: 0 0 auto;
}
.status-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  height: var(--console-collapsed-h);
  padding: 0 12px;
  background: var(--bg-chrome);
  border-top: 1px solid var(--border);
  cursor: pointer;
  user-select: none;
}
.tabs {
  display: flex;
  gap: 2px;
}
.tab {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
}
.tab.active {
  background: var(--bg-active);
  color: var(--accent-ink);
  font-weight: 550;
}
.err-badge {
  margin-left: 4px;
  background: var(--danger);
  color: #fff;
  font-size: 10px;
  border-radius: 999px;
  padding: 0 5px;
}
.last {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  text-align: left;
}
.muted {
  color: var(--text-muted);
}
.mini {
  padding: 2px 8px;
  font-size: 11px;
}
.chev {
  color: var(--text-muted);
  font-size: 12px;
}
/* 浮层不改变主内容的布局高度。 */
.panel {
  position: absolute;
  left: 0;
  right: 0;
  bottom: var(--console-collapsed-h);
  height: min(240px, 36vh);
  background: var(--bg-panel);
  border-top: 1px solid var(--border);
  box-shadow: 0 -6px 18px -6px rgba(17, 24, 33, 0.14);
  display: flex;
  flex-direction: column;
}
.body {
  flex: 1;
  overflow: auto;
  padding: 8px 12px;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}
.log-line {
  display: grid;
  grid-template-columns: 72px 56px 1fr;
  gap: 10px;
  padding: 2px 0;
}
.log-line .lvl {
  font-weight: 550;
}
.log-line.error .lvl {
  color: var(--danger);
}
.log-line.warn .lvl,
.log-line.warning .lvl {
  color: var(--warning);
}
.log-line.info .lvl {
  color: var(--info);
}
</style>
