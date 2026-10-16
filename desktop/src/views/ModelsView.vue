<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import EmptyState from '../components/EmptyState.vue'
import { wsClient } from '../api/ws'
import { DEFAULT_BOX_COLOR } from '../components/labelTypes'
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
  weights_available?: boolean
  downloadable?: boolean
  runtime_available?: boolean
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
const downloadingModelId = ref('')
const importingWeightsModelId = ref('')
let stopDownloadProgress: (() => void) | undefined
let stopClientOpen: (() => void) | undefined

const selected = computed(() => models.value.find((m) => m.model_id === selectedId.value) ?? null)
const yoloRuntimeMissing = computed(() =>
  models.value.some((m) => m.backend === 'yolo' && m.runtime_available === false)
)

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

/** 重新读取本地和仓库模型，并同步当前选择的类别编辑草稿。 */
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

function onModelLibraryChanged(): void {
  void loadList()
}

function resetDraft(): void {
  const map: Record<string, string> = {}
  const colors: Record<string, string> = {}
  for (const c of selected.value?.class_list || []) {
    map[c.class_name] = c.display_name || c.class_name
    colors[c.class_name] = c.color || DEFAULT_BOX_COLOR
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

/** 下载用户选中的内置权重，显示进度/结果并通知其他页面刷新模型状态。 */
async function downloadBuiltin(modelId: string): Promise<void> {
  if (downloadingModelId.value || importingWeightsModelId.value) return
  const model = models.value.find((m) => m.model_id === modelId)
  if (!model) return
  downloadingModelId.value = modelId
  infoMsg.value = `正在下载 ${model.name} 权重…`
  errorMsg.value = ''
  try {
    const resp = await wsClient.request('model.downloadBuiltin', { model_ids: [modelId] }, 10 * 60 * 1000)
    const results = (resp.data as { results?: Array<{ model_id: string; ok: boolean; error?: string }> }).results || []
    const result = results.find((item) => item.model_id === modelId)
    await loadList()
    if (!result?.ok) {
      errorMsg.value = `模型权重下载失败：${result?.error || '后端没有返回下载结果'}`
      infoMsg.value = ''
    } else {
      infoMsg.value = `${model.name} 权重已下载，可以开始推理。`
      window.dispatchEvent(new Event('yolo-models-changed'))
    }
  } catch (e) {
    errorMsg.value = formatError(e)
    infoMsg.value = ''
  } finally {
    downloadingModelId.value = ''
  }
}

/** 为已有模型选择本地权重文件，并交由后端校验、复制和关联。 */
async function attachWeights(modelId: string): Promise<void> {
  if (downloadingModelId.value || importingWeightsModelId.value) return
  const model = models.value.find((item) => item.model_id === modelId)
  if (!model) return

  const api = window.yoloStudio
  if (!api?.selectModelFile) {
    errorMsg.value = '请在桌面端中选择权重文件。'
    return
  }

  errorMsg.value = ''
  infoMsg.value = ''
  try {
    const path = await api.selectModelFile()
    if (!path) return
    importingWeightsModelId.value = modelId
    infoMsg.value = `正在为「${model.name}」导入权重…`
    await wsClient.request('model.attachWeights', { model_id: modelId, weight_path: path })
    await loadList()
    infoMsg.value = `已为「${model.name}」导入并关联权重，可以开始推理。`
    window.dispatchEvent(new Event('yolo-models-changed'))
  } catch (e) {
    errorMsg.value = formatError(e)
    infoMsg.value = ''
  } finally {
    importingWeightsModelId.value = ''
  }
}

/** 从本地权重创建新的模型条目，随后刷新列表并选中新模型。 */
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
  stopClientOpen = wsClient.on('client.open', () => void loadList())
  window.addEventListener('yolo-models-changed', onModelLibraryChanged)
  stopDownloadProgress = wsClient.on('model.download.progress', (msg) => {
    const data = msg.data as { model_id?: string; message?: string } | undefined
    if (data?.model_id === downloadingModelId.value && data.message) infoMsg.value = data.message
  })
})

onUnmounted(() => {
  stopClientOpen?.()
  stopDownloadProgress?.()
  window.removeEventListener('yolo-models-changed', onModelLibraryChanged)
})
</script>

<template>
  <!-- 模型管理页面：浏览模型、下载内置权重、导入权重并编辑类别信息。 -->
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
        <button type="button" class="ghost" :disabled="loading" @click="loadList">
          {{ t('action.refresh') }}
        </button>
      </div>
    </div>

    <p v-if="errorMsg" class="err-text">{{ errorMsg }}</p>
    <p v-if="infoMsg" class="info-text">{{ infoMsg }}</p>
    <p class="hint-text">首次启动会自动安装 Python 推理依赖。模型权重不会自动下载：有官方下载源的模型可下载或重试；其他模型可选择本地权重导入。</p>
    <p v-if="yoloRuntimeMissing" class="runtime-warning">
      YOLO 推理组件尚未准备好。请在首次启动初始化提示中点击「重试初始化」；如果仍失败，可查看初始化日志。
    </p>

    <div class="grid">
      <div class="panel">
        <table class="table">
          <thead>
            <tr>
              <th>{{ t('models.name') }}</th>
              <th>{{ t('models.backend') }}</th>
              <th>{{ t('models.status') }}</th>
              <th>权重</th>
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
              <td class="weights-cell">
                <span
                  class="badge"
                  :class="{
                    ok: m.weights_available !== false && m.runtime_available !== false,
                    missing: m.weights_available === false || m.runtime_available === false
                  }"
                >
                  {{ m.runtime_available === false ? '推理组件缺失' : m.weights_available === false ? (m.downloadable ? '未下载' : t('models.manualImportWeights')) : '已就绪' }}
                </span>
                <div v-if="m.weights_available === false" class="weight-actions">
                  <button
                    v-if="m.downloadable"
                    type="button"
                    class="ghost mini"
                    :disabled="Boolean(downloadingModelId) || Boolean(importingWeightsModelId)"
                    @click.stop="downloadBuiltin(m.model_id)"
                  >
                    {{ downloadingModelId === m.model_id ? '下载中…' : '下载 / 重试' }}
                  </button>
                  <button
                    type="button"
                    class="ghost mini"
                    :disabled="Boolean(downloadingModelId) || Boolean(importingWeightsModelId)"
                    @click.stop="attachWeights(m.model_id)"
                  >
                    {{ importingWeightsModelId === m.model_id ? '导入中…' : '导入权重' }}
                  </button>
                </div>
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
                <span class="swatch" :style="{ background: colorDraft[c.class_name] || c.color || DEFAULT_BOX_COLOR }" />
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
.hint-text {
  color: var(--text-secondary);
  margin: 0;
  font-size: var(--text-sm);
}
.runtime-warning {
  color: var(--danger);
  margin: 0;
  font-size: var(--text-sm);
}
.weights-cell {
  white-space: normal;
}
.weight-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}
.badge.missing {
  color: var(--warning, #a76500);
  background: var(--warning-soft, #fff3d6);
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
