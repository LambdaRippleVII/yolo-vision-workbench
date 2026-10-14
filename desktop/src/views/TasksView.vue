<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import EmptyState from '../components/EmptyState.vue'
import { wsClient } from '../api/ws'
import { formatError } from '../utils/errors'
import type { Envelope } from '../api/protocol'
import { t } from '../locales'

interface TaskItem {
  task_id: string
  type: string
  status: string
  progress: number
  created_at?: string
  finished_at?: string | null
  error?: string | null
  progress_detail?: { done?: number; total?: number; current_item?: string }
  model_ids?: string[]
}

const tasks = ref<TaskItem[]>([])
const loading = ref(false)
const errorMsg = ref('')

const statusMap: Record<string, string> = {
  pending: t('status.pending'),
  running: t('status.running'),
  paused: t('status.paused'),
  completed: t('status.completed'),
  cancelled: t('status.cancelled'),
  failed: t('status.failed')
}

const typeMap: Record<string, string> = {
  image: t('workbench.imageDetect'),
  folder: '文件夹',
  video: t('workbench.videoDetect'),
  stream: t('workbench.cameraLive'),
  pipeline: '管线',
  export: '导出'
}

function statusClass(s: string): string {
  if (s === 'completed') return 'ok'
  if (s === 'failed') return 'err'
  if (s === 'running' || s === 'pending' || s === 'paused') return 'warn'
  return ''
}

function upsertFromEvent(data: Record<string, unknown>): void {
  const id = String(data.task_id || '')
  if (!id) return
  const next: TaskItem = {
    task_id: id,
    type: String(data.type || 'image'),
    status: String(data.status || 'running'),
    progress: Number(data.progress || 0),
    created_at: String(data.created_at || ''),
    finished_at: (data.finished_at as string) || null,
    error: (data.error as string) || null,
    progress_detail: (data.progress_detail as TaskItem['progress_detail']) || {},
    model_ids: (data.model_ids as string[]) || []
  }
  const idx = tasks.value.findIndex((x) => x.task_id === id)
  if (idx >= 0) tasks.value[idx] = { ...tasks.value[idx], ...next }
  else tasks.value.unshift(next)
}

async function refresh(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    const resp = await wsClient.request('task.list', {})
    tasks.value = ((resp.data as { tasks?: TaskItem[] }).tasks ?? []) as TaskItem[]
  } catch (e) {
    errorMsg.value = formatError(e)
  } finally {
    loading.value = false
  }
}

async function cancelTask(id: string): Promise<void> {
  try {
    await wsClient.request('task.cancel', { task_id: id })
    await refresh()
  } catch (e) {
    errorMsg.value = formatError(e)
  }
}

let offs: Array<() => void> = []

onMounted(() => {
  void refresh()
  offs.push(
    wsClient.on('client.open', () => void refresh()),
    wsClient.on('task.progress', (msg: Envelope) => upsertFromEvent(msg.data as Record<string, unknown>)),
    wsClient.on('task.done', (msg: Envelope) => upsertFromEvent(msg.data as Record<string, unknown>)),
    wsClient.on('task.created', (msg: Envelope) => upsertFromEvent(msg.data as Record<string, unknown>))
  )
  const onProject = () => void refresh()
  window.addEventListener('yolo-project-changed', onProject)
  offs.push(() => window.removeEventListener('yolo-project-changed', onProject))
})

onUnmounted(() => {
  offs.forEach((off) => off())
  offs = []
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">{{ t('tasks.title') }}</h1>
      <div class="header-spacer" />
      <button type="button" class="ghost" :disabled="loading" @click="refresh">
        {{ t('action.refresh') }}
      </button>
    </div>

    <p v-if="errorMsg" class="err-text">{{ errorMsg }}</p>

    <div class="panel">
      <table v-if="tasks.length" class="table">
        <thead>
          <tr>
            <th>{{ t('tasks.id') }}</th>
            <th>{{ t('tasks.type') }}</th>
            <th>{{ t('tasks.status') }}</th>
            <th>{{ t('tasks.progress') }}</th>
            <th>{{ t('tasks.created') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasks" :key="task.task_id">
            <td class="num">{{ task.task_id }}</td>
            <td>{{ typeMap[task.type] || task.type }}</td>
            <td>
              <span class="badge" :class="statusClass(task.status)">
                {{ statusMap[task.status] || task.status }}
              </span>
            </td>
            <td>
              <div class="progress">
                <div class="bar" :style="{ width: `${Math.round((task.progress || 0) * 100)}%` }" />
                <span class="num">{{ Math.round((task.progress || 0) * 100) }}%</span>
              </div>
            </td>
            <td class="num">{{ (task.created_at || '').replace('T', ' ').slice(0, 19) }}</td>
            <td>
              <button
                v-if="task.status === 'running' || task.status === 'pending' || task.status === 'paused'"
                type="button"
                class="danger"
                @click="cancelTask(task.task_id)"
              >
                {{ t('action.cancel') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <EmptyState v-else icon="▶" :title="t('tasks.title')" :description="t('tasks.empty')" />
    </div>
  </div>
</template>

<style scoped>
.err-text {
  color: var(--danger);
  margin: 0;
  font-size: var(--text-sm);
}
.progress {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 120px;
}
.progress .bar {
  height: 6px;
  border-radius: 999px;
  background: var(--accent);
  flex: 1;
  max-width: 100px;
  background-color: var(--accent);
}
.progress {
  background: linear-gradient(to right, var(--bg-active), var(--bg-active));
}
.bar {
  background: var(--accent);
}
</style>
