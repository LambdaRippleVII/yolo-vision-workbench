<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EmptyState from '../components/EmptyState.vue'
import { wsClient } from '../api/ws'
import { formatError } from '../utils/errors'
import { t } from '../locales'

interface ClassItem {
  class_id: number
  class_name: string
  display_name: string
  color?: string
}

interface ModelItem {
  source?: { dataset?: string; author?: string; license?: string; model?: string; repo?: string }
  source_dir?: string
  model_id: string
  name: string
  backend: string
  task: string
  model_path: string
  loaded: boolean
  class_list: ClassItem[]
  class_display?: Record<string, string>
  class_colors?: Record<string, string>
  class_color_mode?: 'auto' | 'manual'
}

const tab = ref<'local' | 'repository'>('local')
const models = ref<ModelItem[]>([])
const loading = ref(false)
const errorMsg = ref('')
const selectedId = ref('')
const displayDraft = ref<Record<string, string>>({})
const colorDraft = ref<Record<string, string>>({})
const colorMode = ref<'auto' | 'manual'>('auto')
const saving = ref(false)
const filterText = ref('')
const infoMsg = ref('')

const selected = computed(() => models.value.find((m) => m.model_id === selectedId.value) ?? null)

const visibleClasses = computed(() => {
  const list = selected.value?.class_list || []
  const k = filterText.value.trim().toLowerCase()
  if (!k) return list
  return list.filter(
    (c) =>
      c.class_name.toLowerCase().includes(k) ||
      (c.display_name || '').includes(filterText.value.trim()) ||
      (c.display_name || '').toLowerCase().includes(k)
  )
})

async function loadList(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    const resp = await wsClient.request('model.list', { include_repository: true })
    models.value = ((resp.data as { models?: ModelItem[] }).models ?? []) as ModelItem[]
    if (!selectedId.value && models.value.length) selectedId.value = models.value[0].model_id
    resetDraft()
  } catch (e) {
    errorMsg.value = formatError(e)
  } finally {
    loading.value = false
  }
}

function resetDraft(): void {
  const map: Record<string, string> = {}
  const colors: Record<string, string> = {}
  for (const c of selected.value?.class_list || []) {
    map[c.class_name] = c.display_name || c.class_name
    colors[c.class_name] = c.color || '#2F6FED'
  }
  displayDraft.value = map
  colorDraft.value = colors
  colorMode.value = selected.value?.class_color_mode === 'manual' ? 'manual' : 'auto'
}

async function saveDisplay(): Promise<void> {
  if (!selected.value) return
  saving.value = true
  errorMsg.value = ''
  try {
    await wsClient.request('model.classDisplay', {
      model_id: selected.value.model_id,
      class_display: displayDraft.value,
      class_colors: colorMode.value === 'manual' ? colorDraft.value : {},
      class_color_mode: colorMode.value
    })
    await loadList()
  } catch (e) {
    errorMsg.value = formatError(e)
  } finally {
    saving.value = false
  }
}

async function downloadBuiltin(): Promise<void> {
  infoMsg.value = '正在拉取内置模型权重…'
  errorMsg.value = ''
  try {
    const resp = await wsClient.request('model.downloadBuiltin', {})
    const results = (resp.data as { results?: Array<{ model_id: string; ok: boolean; error?: string }> }).results || []
    const failed = results.filter((r) => !r.ok)
    await loadList()
    if (failed.length) {
      errorMsg.value =
        '部分模型下载失败：' + failed.map((f) => `${f.model_id}（${f.error}）`).join('；')
    } else {
      infoMsg.value = `内置模型权重已就绪（${results.length}）`
    }
  } catch (e) {
    errorMsg.value = formatError(e)
  }
}

async function importModel(): Promise<void> {
  const api = window.yoloStudio
  if (!api?.selectModelFile) {
    errorMsg.value = '请在桌面端中选择模型文件'
    return
  }
  const path = await api.selectModelFile()
  if (!path) return
  errorMsg.value = ''
  try {
    const resp = await wsClient.request('model.import', {
      weight_path: path,
      name: path.split(/[\\/]/).pop()?.replace(/\.[^.]+$/, '')
    })
    const m = (resp.data as { model?: { model_id: string; class_list?: unknown[] } }).model
    await loadList()
    if (m) {
      selectedId.value = m.model_id
      resetDraft()
      infoMsg.value = `已导入 ${m.model_id}（${(m.class_list || []).length} 类）`
    }
  } catch (e) {
    errorMsg.value = formatError(e)
  }
}

onMounted(() => {
  void loadList()
  wsClient.on('client.open', () => void loadList())
})
</script>

<template>
  <div class="page models-page">
    <div class="page-header">
      <h1 class="page-title">{{ t('models.title') }}</h1>
      <div class="page-toolbar">
        <button type="button" :class="{ primary: tab === 'local' }" @click="tab = 'local'">
          {{ t('models.local') }}
        </button>
        <button type="button" :class="{ primary: tab === 'repository' }" @click="tab = 'repository'">
          {{ t('models.repository') }}
        </button>
        <button type="button" class="primary" @click="importModel">
          {{ t('models.import') }}
        </button>
        <button type="button" class="ghost" @click="downloadBuiltin">{{ t('models.download') }}</button>
        <button type="button" class="ghost" :disabled="loading" @click="loadList">
          {{ t('action.refresh') }}
        </button>
      </div>
    </div>

    <p v-if="errorMsg" class="err-text">{{ errorMsg }}</p>
    <p v-if="infoMsg" class="info-text">{{ infoMsg }}</p>

    <div class="grid">
      <div class="panel">
        <table class="table">
          <thead>
            <tr>
              <th>{{ t('models.name') }}</th>
              <th>{{ t('models.backend') }}</th>
              <th>{{ t('models.status') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="m in models"
              :key="m.model_id"
              :class="{ 'row-selected': m.model_id === selectedId }"
              @click="selectedId = m.model_id; resetDraft()"
            >
              <td>{{ m.name }}<div class="src-meta">{{ m.source?.dataset }} · {{ m.source?.model }} · {{ m.source?.license }}</div></td>
              <td>{{ m.backend }}</td>
              <td>
                <span class="badge" :class="m.loaded ? 'ok' : ''">
                  {{ m.loaded ? t('models.loaded') : t('models.unloaded') }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-if="!models.length" icon="◈" :title="t('models.title')" :description="t('models.empty')" />
      </div>

      <div class="panel map-panel">
        <div class="map-head">
          <div class="map-head-row">
            <h2 class="panel-title">{{ t('models.classMapTitle') }}</h2>
            <div class="color-mode">
              <label class="seg">
                <input v-model="colorMode" type="radio" value="auto" />
                <span>{{ t('models.colorAuto') }}</span>
              </label>
              <label class="seg">
                <input v-model="colorMode" type="radio" value="manual" />
                <span>{{ t('models.colorManual') }}</span>
              </label>
            </div>
            <input v-model="filterText" class="search" :placeholder="'搜索类别…'" />
            <button type="button" class="primary save-btn" :disabled="saving || !selected" @click="saveDisplay">
              {{ t('models.saveDisplay') }}
            </button>
          </div>
        </div>
        <div class="panel-body map-body">
          <p v-if="!selected" class="muted">{{ t('models.selectModelHint') }}</p>
          <template v-else>
            <p class="muted">
              {{ selected.name }} · {{ selected.class_list.length }} 类 · {{ t('models.displayHint') }}
            </p>
            <div class="map-list">
              <div v-for="c in visibleClasses" :key="c.class_name" class="map-row">
                <span class="swatch" :style="{ background: colorDraft[c.class_name] || c.color || '#2F6FED' }" />
                <input
                  v-if="colorMode === 'manual'"
                  v-model="colorDraft[c.class_name]"
                  type="color"
                  class="color"
                />
                <span v-else class="color-fake">●</span>
                <span class="orig num">{{ c.class_name }}</span>
                <span class="arrow">→</span>
                <input v-model="displayDraft[c.class_name]" class="disp" :placeholder="c.class_name" />
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.models-page {
  overflow: hidden;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1.15fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.grid > .panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.err-text {
  color: var(--danger);
  margin: 0;
  font-size: var(--text-sm);
}
.info-text {
  color: var(--success);
  margin: 0;
  font-size: var(--text-sm);
}
.row-selected td {
  background: var(--bg-active);
}
.map-head {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
}
.map-head-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.color-mode {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-inset);
}
.seg {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  font-size: var(--text-sm);
  cursor: pointer;
  color: var(--text-secondary);
}
.seg:has(input:checked) {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 550;
}
.seg input {
  display: none;
}
.search {
  height: 30px;
  width: 150px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0 10px;
  background: var(--bg-panel);
  color: var(--text-primary);
  font-size: var(--text-sm);
}
.save-btn {
  margin-left: auto;
}
.map-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.map-list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-right: 2px;
}
.map-row {
  display: grid;
  grid-template-columns: 14px 28px 1fr 16px 1fr;
  gap: 8px;
  align-items: center;
  font-size: var(--text-sm);
}
.swatch {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  border: 1px solid var(--border);
}
.color {
  width: 28px;
  height: 24px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 4px;
}
.color-fake {
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
}
.orig {
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.arrow {
  color: var(--text-muted);
  text-align: center;
}
.disp {
  height: 28px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0 8px;
  background: var(--bg-panel);
  color: var(--text-primary);
}
.muted {
  color: var(--text-muted);
  font-size: var(--text-sm);
}
</style>
