<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import EmptyState from '../components/EmptyState.vue'
import { wsClient } from '../api/ws'
import { formatError } from '../utils/errors'
import type { Envelope } from '../api/protocol'
import { t } from '../locales'

interface ProjectItem {
  project_id: string
  name: string
  root_path?: string
  description?: string
  created_at?: string | null
  updated_at?: string | null
}

const projects = ref<ProjectItem[]>([])
const currentId = ref('default')
const loading = ref(false)
const errorMsg = ref('')
const newName = ref('')
const creating = ref(false)

async function refresh(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    const resp = await wsClient.request('project.list', {})
    const data = resp.data as { projects?: ProjectItem[]; current_project_id?: string }
    projects.value = data.projects ?? []
    currentId.value = data.current_project_id || 'default'
  } catch (e) {
    errorMsg.value = formatError(e)
  } finally {
    loading.value = false
  }
}

async function openProject(id: string): Promise<void> {
  errorMsg.value = ''
  try {
    await wsClient.request('project.open', { project_id: id })
    await refresh()
    window.dispatchEvent(new CustomEvent('yolo-project-changed', { detail: { project_id: id } }))
  } catch (e) {
    errorMsg.value = formatError(e)
  }
}

async function createProject(): Promise<void> {
  const name = newName.value.trim()
  if (!name) return
  creating.value = true
  errorMsg.value = ''
  try {
    await wsClient.request('project.create', { name })
    newName.value = ''
    await refresh()
    window.dispatchEvent(new CustomEvent('yolo-project-changed', { detail: { created: name } }))
  } catch (e) {
    errorMsg.value = formatError(e)
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  void refresh()
  wsClient.on('client.open', () => void refresh())
})
onUnmounted(() => {
  /* noop */
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">{{ t('projects.title') }}</h1>
      <div class="header-spacer" />
      <button type="button" class="ghost" :disabled="loading" @click="refresh">
        {{ t('action.refresh') }}
      </button>
    </div>

    <div class="create-row">
      <input
        v-model="newName"
        class="text-input"
        :placeholder="t('projects.namePlaceholder')"
        @keyup.enter="createProject"
      />
      <button type="button" class="primary" :disabled="creating || !newName.trim()" @click="createProject">
        {{ t('action.newProject') }}
      </button>
    </div>

    <p v-if="errorMsg" class="err-text">{{ errorMsg }}</p>

    <div class="panel">
      <div class="panel-head">
        <h2 class="panel-title">{{ t('projects.recent') }}</h2>
      </div>
      <table v-if="projects.length" class="table">
        <thead>
          <tr>
            <th>{{ t('projects.name') }}</th>
            <th>ID</th>
            <th>{{ t('projects.path') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in projects" :key="p.project_id" :class="{ 'row-current': p.project_id === currentId }">
            <td>
              {{ p.name }}
              <span v-if="p.project_id === currentId" class="badge ok">{{ t('projects.current') }}</span>
            </td>
            <td class="num">{{ p.project_id }}</td>
            <td class="num path">{{ p.root_path }}</td>
            <td>
              <button
                v-if="p.project_id !== currentId"
                type="button"
                class="primary"
                @click="openProject(p.project_id)"
              >
                {{ t('action.openProject') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <EmptyState
        v-else
        icon="▤"
        :title="t('projects.title')"
        :description="t('projects.empty')"
        :action-label="t('action.newProject')"
        @action="createProject"
      />
    </div>
  </div>
</template>

<style scoped>
.create-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.text-input {
  height: 32px;
  width: 240px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-panel);
  color: var(--text-primary);
  padding: 0 10px;
  font-size: var(--text-md);
}
.err-text {
  color: var(--danger);
  margin: 0;
  font-size: var(--text-sm);
}
.row-current td {
  background: var(--bg-active);
}
.path {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
