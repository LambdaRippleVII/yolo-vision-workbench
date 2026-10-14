<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import CanvasStage, { type BoxObject } from '../components/CanvasStage.vue'
import type { LabelSettings } from '../components/labelTypes'
import { defaultLabelSettings } from '../components/labelTypes'
import ClassPickerModal from '../components/ClassPickerModal.vue'
import MoreSettingsModal from '../components/MoreSettingsModal.vue'
import LabelConfigModal from '../components/LabelConfigModal.vue'
import EmptyState from '../components/EmptyState.vue'
import { wsClient } from '../api/ws'
import { formatError } from '../utils/errors'
import { t } from '../locales'

interface ModelItem {
  model_id: string
  name: string
  loaded: boolean
  class_list: Array<{ class_id: number; class_name: string; display_name: string }>
}

interface GalleryItem {
  path: string
  url: string
  thumb?: string
  name: string
  objects?: BoxObject[]
  status?: 'idle' | 'processing' | 'done' | 'empty'
}

const mediaPath = ref('')
const mediaKind = ref<'image' | 'folder' | 'unknown'>('unknown')
const imageUrl = ref('')
const objects = ref<BoxObject[]>([])
const selectedId = ref<number | null>(null)
const models = ref<ModelItem[]>([])
const selectedModels = ref<string[]>([])
const classFilter = ref<Record<string, string[]>>({})
const conf = ref(0.45)
const labelTemplate = ref('{id}:{class}')
const maxSide = ref(1280)
const running = ref(false)
const errorMsg = ref('')
const infoMsg = ref('')
const lastImageTaskId = ref('')
const showMore = ref(false)
const showLabelCfg = ref(false)
const classModalModel = ref('')

const labelSettings = ref<LabelSettings>(defaultLabelSettings())
const gallery = ref<GalleryItem[]>([])
const currentGalleryIndex = ref(0)
const dragging = ref(false)
const selectedGalleryPaths = ref<Set<string>>(new Set())
const sessionMode = ref<'temp' | 'project'>('temp')

const resultItems = computed(() =>
  objects.value.map((o) => ({
    ...o,
    display: o.display_name || o.class_name,
    confText: `${Math.round(o.confidence * 100)}%`
  }))
)

const activeModels = computed(() => models.value.filter((m) => selectedModels.value.includes(m.model_id)))

const classModalModelItem = computed(() =>
  models.value.find((m) => m.model_id === classModalModel.value) || null
)

function setErr(e: unknown): void {
  errorMsg.value = formatError(e)
}

async function loadModels(): Promise<void> {
  try {
    const resp = await wsClient.request('model.list', {})
    models.value = ((resp.data as { models?: ModelItem[] }).models ?? []) as ModelItem[]
  } catch (e) {
    const msg = formatError(e)
    if (!msg.includes('通信未就绪')) errorMsg.value = msg
  }
}

async function ensureModelLoaded(modelId: string): Promise<void> {
  try {
    const resp = await wsClient.request('model.load', { model_ids: [modelId] })
    const item = ((resp.data as { models?: ModelItem[] }).models ?? [])[0]
    if (item) {
      const idx = models.value.findIndex((m) => m.model_id === modelId)
      if (idx >= 0) models.value[idx] = { ...models.value[idx], ...item }
    }
    await loadModels()
  } catch (e) {
    setErr(e)
  }
}

async function onToggleModel(modelId: string, checked: boolean): Promise<void> {
  if (checked) {
    if (!selectedModels.value.includes(modelId)) selectedModels.value = [...selectedModels.value, modelId]
    await ensureModelLoaded(modelId)
    const m = models.value.find((x) => x.model_id === modelId)
    if (m && !classFilter.value[modelId]) {
      classFilter.value = {
        ...classFilter.value,
        [modelId]: m.class_list.map((c) => c.class_name)
      }
    }
  } else {
    selectedModels.value = selectedModels.value.filter((x) => x !== modelId)
  }
}

function onClassUpdate(modelId: string, list: string[]): void {
  classFilter.value = { ...classFilter.value, [modelId]: list }
}

function openClassModal(modelId: string): void {
  classModalModel.value = modelId
}

function looksLikeImagePath(p: string): boolean {
  return /\.(jpg|jpeg|png|bmp|webp|tif|tiff)$/i.test(p)
}

function looksLikeFolderPath(p: string): boolean {
  if (!p) return false
  if (looksLikeImagePath(p)) return false
  // Windows folder often has no extension
  return !/\.[a-z0-9]+$/i.test(p)
}

async function pickFolder(): Promise<void> {
  const api = window.yoloStudio
  errorMsg.value = ''
  infoMsg.value = ''
  gallery.value = []
  selectedGalleryPaths.value = new Set()
  if (!api?.selectFolder) {
    errorMsg.value = '请在桌面端中选择文件夹'
    return
  }
  const path = await api.selectFolder()
  if (!path) return
  mediaPath.value = path
  mediaKind.value = 'folder'
  imageUrl.value = ''
  objects.value = []
  // only list album — do NOT run detect
  await loadFolderAlbum(path)
}

async function pickImage(): Promise<void> {
  const api = window.yoloStudio
  errorMsg.value = ''
  infoMsg.value = ''
  gallery.value = []
  if (!api?.selectImage) {
    errorMsg.value = '请在桌面端中选择图片'
    return
  }
  const path = await api.selectImage()
  if (!path) return
  mediaPath.value = path
  mediaKind.value = 'image'
  if (api.readImageBase64) imageUrl.value = (await api.readImageBase64(path)) || ''
  objects.value = []
  selectedId.value = null
}

async function loadFolderAlbum(path: string): Promise<void> {
  try {
    const resp = await wsClient.request('media.listFolder', {
      folder_path: path,
      with_thumbs: true
    })
    const items = ((resp.data as { items?: Array<{ path: string; name: string; thumb_url?: string }> }).items ??
      []) as Array<{ path: string; name: string; thumb_url?: string }>
    gallery.value = items.map((it) => ({
      path: it.path,
      url: '', // full image loaded on select
      thumb: it.thumb_url || '',
      name: it.name,
      status: 'idle'
    }))
    if (gallery.value.length) {
      await selectGallery(0)
      infoMsg.value = `已加载 ${gallery.value.length} 张图片，点击「开始推理」逐张识别`
    } else {
      infoMsg.value = '该文件夹下没有可识别的图片'
    }
  } catch (e) {
    setErr(e)
  }
}

async function loadFullImage(item: GalleryItem): Promise<void> {
  const api = window.yoloStudio
  if (api?.readImageBase64) {
    const full = await api.readImageBase64(item.path)
    if (full) {
      item.url = full
      imageUrl.value = full
      return
    }
  }
  // fallback to thumb only if full read fails
  if (item.thumb) {
    item.url = item.thumb
    imageUrl.value = item.thumb
  }
}

async function selectGallery(i: number): Promise<void> {
  currentGalleryIndex.value = i
  const item = gallery.value[i]
  if (!item) return
  mediaPath.value = item.path
  mediaKind.value = 'image'
  if (!item.url) {
    await loadFullImage(item)
  } else {
    imageUrl.value = item.url
  }
  objects.value = item.objects || []
  selectedId.value = objects.value.length ? objects.value[0].id : null
}

function toggleGallerySelect(path: string, ev?: MouseEvent): void {
  if (ev?.shiftKey && currentGalleryIndex.value >= 0) {
    const from = currentGalleryIndex.value
    const to = gallery.value.findIndex((g) => g.path === path)
    if (to >= 0) {
      const lo = Math.min(from, to)
      const hi = Math.max(from, to)
      const set = new Set(selectedGalleryPaths.value)
      for (let i = lo; i <= hi; i++) {
        const p = gallery.value[i]?.path
        if (p) set.add(p)
      }
      selectedGalleryPaths.value = set
      return
    }
  }
  const set = new Set(selectedGalleryPaths.value)
  if (set.has(path)) set.delete(path)
  else set.add(path)
  selectedGalleryPaths.value = set
}

function selectAllGallery(): void {
  selectedGalleryPaths.value = new Set(gallery.value.map((g) => g.path))
}

function clearGallerySelection(): void {
  selectedGalleryPaths.value = new Set()
}

async function runFolder(path: string, filePaths?: string[]): Promise<void> {
  if (!selectedModels.value.length) {
    if (models.value.length) {
      const first = models.value[0].model_id
      await onToggleModel(first, true)
    }
  }
  if (!selectedModels.value.length) {
    errorMsg.value = t('workbench.noModel')
    return
  }
  // album must already be loaded; if not, load first without auto-detect
  if (!gallery.value.length) {
    await loadFolderAlbum(path)
  }
  if (!gallery.value.length) {
    errorMsg.value = '文件夹内没有图片（支持 jpg/png/bmp/webp 等）'
    return
  }
  const targets = filePaths && filePaths.length ? filePaths : [...selectedGalleryPaths.value]
  if (filePaths && filePaths.length) {
    // explicit list
  } else if (!selectedGalleryPaths.value.size) {
    // none selected → all images
    selectedGalleryPaths.value = new Set(gallery.value.map((g) => g.path))
  }
  const sendList = targets.length
    ? targets
    : gallery.value.map((g) => g.path)

  for (const g of gallery.value) {
    if (sendList.includes(g.path)) {
      g.status = 'idle'
      g.objects = []
    }
  }
  try {
    const resp = await wsClient.request('detect.folder', {
      folder_path: path,
      file_paths: sendList,
      model_ids: selectedModels.value,
      overrides: {
        conf: conf.value,
        class_filter: classFilter.value,
        max_side: maxSide.value
      }
    })
    const task = (resp.data as { task?: { task_id?: string } }).task
    lastImageTaskId.value = task?.task_id || ''
    infoMsg.value = `批量识别中 0/${sendList.length}`
  } catch (e) {
    setErr(e)
  }
}

async function buildGalleryFromFolder(_path: string): Promise<void> {
  // Folder gallery is filled incrementally from task.progress frames when available
  // Fallback: if dropped File objects exist they were already added
}

async function fileToTempPath(file: File): Promise<{ path: string; url: string } | null> {
  const api = window.yoloStudio
  // Prefer real path (drag from Explorer in Electron)
  const realPath = (file as File & { path?: string }).path
  if (realPath && api?.readImageBase64) {
    const url = (await api.readImageBase64(realPath)) || ''
    return { path: realPath, url }
  }
  if (!api?.writeTempImage) {
    // browser fallback: object URL only (cannot send to backend as path)
    return { path: file.name, url: URL.createObjectURL(file) }
  }
  const b64 = await new Promise<string>((resolveB64, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result || '')
      resolveB64(result.replace(/^data:[^,]+,/, ''))
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
  const saved = await api.writeTempImage({ name: file.name || 'paste.png', base64: b64 })
  if (!saved) return null
  return { path: saved, url: `data:image/png;base64,${b64}` }
}

function addFilesToGallery(files: File[]): void {
  void (async () => {
    for (const f of files) {
      if (!f.type.startsWith('image/')) continue
      const saved = await fileToTempPath(f)
      if (!saved) continue
      const item: GalleryItem = {
        path: saved.path,
        url: saved.url,
        name: f.name || saved.path.split(/[\\/]/).pop() || 'image'
      }
      gallery.value.push(item)
      if (gallery.value.length === 1) {
        currentGalleryIndex.value = 0
        imageUrl.value = item.url
        mediaPath.value = item.path
      }
    }
    infoMsg.value = `已导入 ${gallery.value.length} 张，可点击缩略图或直接推理`
  })()
}

function selectGalleryLocalPlaceholder(): void {
  /* replaced by async selectGallery above */
}

function resolveDropPath(file: File): string {
  const api = window.yoloStudio
  if (api?.getPathForFile) {
    const p = api.getPathForFile(file)
    if (p) return p
  }
  return (file as File & { path?: string }).path || ''
}

function isProbablyDir(p: string): boolean {
  if (!p) return false
  if (looksLikeImagePath(p)) return false
  // no extension → folder
  return !/\.[a-z0-9]+$/i.test(p)
}

async function handleDrop(ev: DragEvent): Promise<void> {
  dragging.value = false
  errorMsg.value = ''
  infoMsg.value = ''
  const dt = ev.dataTransfer
  if (!dt) return

  const files = dt.files
  if (!files || !files.length) {
    // try items / entries
    const items = dt.items
    if (items?.length) {
      for (const item of Array.from(items)) {
        const entry = item.webkitGetAsEntry?.()
        if (entry && (entry as FileSystemEntry).isDirectory) {
          const f = item.getAsFile()
          const p = f ? resolveDropPath(f) : ''
          if (p) {
            mediaPath.value = p
            mediaKind.value = 'folder'
            await runFolder(p)
            return
          }
        } else if (entry && (entry as FileSystemEntry).isFile) {
          const f = item.getAsFile()
          if (f) addFilesToGallery([f])
        }
      }
    }
    return
  }

  const list = Array.from(files)
  const resolved: Array<{ file: File; path: string }> = list.map((f) => ({
    file: f,
    path: resolveDropPath(f)
  }))

  // single folder drop
  if (resolved.length === 1) {
    const one = resolved[0]
    if (isProbablyDir(one.path) || !one.file.type) {
      if (one.path && isProbablyDir(one.path)) {
        mediaPath.value = one.path
        mediaKind.value = 'folder'
        imageUrl.value = ''
        objects.value = []
        gallery.value = []
        selectedGalleryPaths.value = new Set()
        await loadFolderAlbum(one.path)
        return
      }
    }
    if (one.path && looksLikeImagePath(one.path)) {
      mediaPath.value = one.path
      mediaKind.value = 'image'
      const api = window.yoloStudio
      if (api?.readImageBase64) {
        imageUrl.value = (await api.readImageBase64(one.path)) || ''
      }
      gallery.value = [
        {
          path: one.path,
          url: imageUrl.value,
          thumb: imageUrl.value,
          name: one.path.split(/[\\/]/).pop() || 'image',
          status: 'idle'
        }
      ]
      currentGalleryIndex.value = 0
      objects.value = []
      infoMsg.value = '已拖入 1 张图片'
      return
    }
  }

  // multiple images or mixed
  const imagePaths = resolved.filter((x) => x.path && looksLikeImagePath(x.path))
  const dirPaths = resolved.filter((x) => x.path && isProbablyDir(x.path))

  if (dirPaths.length === 1 && !imagePaths.length) {
    mediaPath.value = dirPaths[0].path
    mediaKind.value = 'folder'
    await loadFolderAlbum(dirPaths[0].path)
    return
  }

  if (imagePaths.length) {
    for (const x of imagePaths) {
      const api = window.yoloStudio
      const url = api?.readImageBase64 ? await api.readImageBase64(x.path) : ''
      gallery.value.push({
        path: x.path,
        url: url || '',
        thumb: url || '',
        name: x.path.split(/[\\/]/).pop() || 'img',
        status: 'idle'
      })
    }
    if (gallery.value.length) await selectGallery(0)
    infoMsg.value = `已拖入 ${imagePaths.length} 张图片`
    return
  }

  // last resort: image files without path (clipboard-like)
  addFilesToGallery(list.filter((f) => f.type.startsWith('image/')))
}

async function handlePaste(ev: ClipboardEvent): Promise<void> {
  const items = ev.clipboardData?.items
  if (!items) return
  for (const item of Array.from(items)) {
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) {
        addFilesToGallery([file])
        break
      }
    }
  }
}

async function startInfer(): Promise<void> {
  if (!mediaPath.value) {
    errorMsg.value = t('workbench.canvasHint')
    return
  }
  // folder path must never go through detect.image
  if (mediaKind.value === 'folder' || looksLikeFolderPath(mediaPath.value)) {
    const paths = [...selectedGalleryPaths.value]
    await runFolder(mediaPath.value, paths.length ? paths : undefined)
    return
  }
  if (!selectedModels.value.length) {
    errorMsg.value = t('workbench.noModel')
    return
  }
  running.value = true
  errorMsg.value = ''
  infoMsg.value = ''
  try {
    const resp = await wsClient.request('detect.image', {
      media_path: mediaPath.value,
      model_ids: selectedModels.value,
      overrides: {
        conf: conf.value,
        class_filter: classFilter.value,
        label_template: labelTemplate.value,
        max_side: maxSide.value
      }
    })
    const data = resp.data as {
      task?: { task_id?: string }
      frame?: { objects?: BoxObject[] }
    }
    lastImageTaskId.value = data.task?.task_id || ''
    objects.value = data.frame?.objects ?? []
    if (objects.value.length) selectedId.value = objects.value[0].id
    const gi = gallery.value[currentGalleryIndex.value]
    if (gi) gi.objects = objects.value
  } catch (e) {
    setErr(e)
  } finally {
    running.value = false
  }
}

async function saveAnnotated(): Promise<void> {
  const api = window.yoloStudio
  if (!mediaPath.value) {
    errorMsg.value = '请先选择并识别图片'
    return
  }
  if (!api?.saveImage) {
    errorMsg.value = '请在桌面端中保存'
    return
  }
  const out = (await api.saveImage((gallery.value[currentGalleryIndex.value]?.name || 'result').replace(/\.[^.]+$/, '') + '_识别.jpg')) || ''
  if (!out) return
  try {
    const resp = await wsClient.request('export.image', {
      source_path: mediaPath.value,
      output_path: out,
      task_id: lastImageTaskId.value,
      frame_id: 0,
      objects: objects.value,
      label_template: labelTemplate.value
    })
    infoMsg.value = `已保存：${(resp.data as { output_path?: string }).output_path || out}`
  } catch (e) {
    setErr(e)
  }
}

async function pickLocalModel(): Promise<void> {
  const api = window.yoloStudio
  if (!api?.selectModelFile) {
    errorMsg.value = '请在桌面端中选择模型文件'
    return
  }
  const path = await api.selectModelFile()
  if (!path) return
  try {
    const resp = await wsClient.request('model.load', { external_path: path, backend: 'yolo' })
    const item = ((resp.data as { models?: ModelItem[] }).models ?? [])[0]
    if (item) {
      await loadModels()
      await onToggleModel(item.model_id, true)
      infoMsg.value = `已加载临时模型：${item.name}`
    }
  } catch (e) {
    setErr(e)
  }
}

function toggleVisible(id: number): void {
  const o = objects.value.find((x) => x.id === id)
  if (!o) return
  const next = o.visible === false
  o.visible = next
  if (!lastImageTaskId.value) return
  void wsClient
    .request('ops.setVisible', {
      task_id: lastImageTaskId.value,
      frame_id: 0,
      object_id: id,
      model_id: o.model_id,
      visible: next
    })
    .catch((e) => setErr(e))
}

function onGlobalDragOver(ev: DragEvent): void {
  ev.preventDefault()
  dragging.value = true
}

async function onGlobalDrop(ev: DragEvent): Promise<void> {
  ev.preventDefault()
  await handleDrop(ev)
}

onMounted(() => {
  void loadModels()
  window.addEventListener('paste', handlePaste)
  window.addEventListener('dragover', onGlobalDragOver)
  window.addEventListener('drop', onGlobalDrop)
  wsClient.on('client.open', () => {
    errorMsg.value = ''
    void loadModels()
  })
  // folder task results as gallery
  wsClient.on('task.progress', (msg: { data?: Record<string, unknown> }) => {
    void (async () => {
      const d = (msg.data || {}) as {
        type?: string
        progress_detail?: { done?: number; total?: number; current_item?: string; processing_path?: string }
        frame?: {
          media_path?: string
          objects?: BoxObject[]
          status?: string
          index?: number
          total?: number
        }
      }
      if (d.type !== 'folder') return
      const frame = d.frame
      const detail = d.progress_detail || {}
      if (frame?.media_path) {
        const path = frame.media_path
        let item = gallery.value.find((g) => g.path === path)
        if (!item) {
          item = {
            path,
            url: '',
            name: path.split(/[\\/]/).pop() || path,
            status: 'idle'
          }
          gallery.value.push(item)
        }
        if (frame.status === 'processing') {
          item.status = 'processing'
        } else if (frame.status === 'done') {
          item.status = 'done'
          item.objects = frame.objects || []
          const idx = gallery.value.findIndex((g) => g.path === path)
          if (idx >= 0) {
            currentGalleryIndex.value = idx
            await loadFullImage(item)
            mediaPath.value = item.path
            objects.value = item.objects || []
            selectedId.value = objects.value.length ? objects.value[0].id : null
          }
        }
      } else if (detail.processing_path) {
        let item = gallery.value.find((g) => g.path === detail.processing_path)
        if (!item) {
          item = {
            path: detail.processing_path,
            url: '',
            name: detail.current_item || detail.processing_path,
            status: 'processing'
          }
          gallery.value.push(item)
        } else {
          item.status = 'processing'
        }
      }
      const done = detail.done ?? 0
      const total = detail.total ?? gallery.value.length
      infoMsg.value = `批量识别 ${done}/${total}`
    })()
  })
  wsClient.on('task.done', (msg: { data?: Record<string, unknown> }) => {
    const d = (msg.data || {}) as { type?: string; status?: string }
    if (d.type === 'folder' && d.status === 'completed') {
      infoMsg.value = '文件夹识别完成'
      for (const g of gallery.value) {
        if (g.status === 'processing') g.status = 'done'
      }
    }
    if (d.type === 'folder' && d.status === 'failed') {
      errorMsg.value = '文件夹识别失败，请查看日志'
    }
  })
})
onUnmounted(() => {
  window.removeEventListener('paste', handlePaste)
  window.removeEventListener('dragover', onGlobalDragOver)
  window.removeEventListener('drop', onGlobalDrop)
})
</script>

<template>
  <div
    class="page image-page"
    :class="{ dragging }"
    @dragover.prevent="dragging = true"
    @dragleave.prevent="dragging = false"
    @drop.prevent="handleDrop"
  >
    <div class="page-header">
      <h1 class="page-title">{{ t('workbench.imageDetect') }}</h1>
      <div class="page-toolbar">
        <button type="button" class="primary" @click="pickImage">{{ t('action.selectImage') }}</button>
        <button type="button" @click="pickFolder">{{ t('action.selectFolder') }}</button>
        <button
          type="button"
          class="primary"
          :disabled="running || !mediaPath || !selectedModels.length"
          @click="startInfer"
        >
          {{ running ? t('status.running') : t('action.startInfer') }}
        </button>
        <button type="button" :disabled="!objects.length" @click="saveAnnotated">
          {{ t('action.saveImage') }}
        </button>
        <button type="button" @click="showMore = true">{{ t('action.moreSettings') }}</button>
        <button type="button" @click="pickLocalModel">{{ t('action.loadLocalModel') }}</button>
      </div>
    </div>

    <div class="sub">
      <span class="path num">{{ mediaPath || '可拖入图片/文件夹，或 Ctrl+V 粘贴图片' }}</span>
      <label class="lbl">{{ t('workbench.confidence') }}</label>
      <input v-model.number="conf" type="number" min="0" max="1" step="0.05" class="num-input" />
      <label class="lbl">{{ t('workbench.labelTemplate') }}</label>
      <button type="button" @click="showLabelCfg = true">{{ t('action.labelConfig') }}</button>
      <label class="lbl">{{ t('workbench.sessionMode') }}</label>
      <select v-model="sessionMode" class="sel">
        <option value="temp">{{ t('workbench.modeTemp') }}</option>
        <option value="project">{{ t('workbench.modeProject') }}</option>
      </select>
    </div>

    <p v-if="errorMsg" class="err-text">{{ errorMsg }}</p>
    <p v-if="infoMsg" class="muted-line">{{ infoMsg }}</p>

    <div class="work-grid">
      <div class="canvas-panel">
        <CanvasStage
          v-if="imageUrl"
          :image-url="imageUrl"
          :objects="objects"
          :selected-id="selectedId"
          :label-template="labelTemplate"
          :label-settings="labelSettings"
          @select="(id) => (selectedId = id)"
        />
        <EmptyState
          v-else
          icon="▣"
          :title="t('workbench.imageDetect')"
          :description="t('workbench.dropHint')"
          :action-label="t('action.selectImage')"
          @action="pickImage"
        />
      </div>
      <div class="side">
        <section class="panel">
          <div class="panel-head"><h2 class="panel-title">{{ t('workbench.modelSelect') }}</h2></div>
          <div class="panel-body models">
            <label v-for="m in models" :key="m.model_id" class="row">
              <input
                type="checkbox"
                :checked="selectedModels.includes(m.model_id)"
                @change="onToggleModel(m.model_id, ($event.target as HTMLInputElement).checked)"
              />
              <span class="name">{{ m.name }}</span>
              <span class="badge" :class="m.loaded ? 'ok' : ''">
                {{ m.loaded ? t('models.loaded') : t('models.unloaded') }}
              </span>
            </label>
          </div>
        </section>

        <section v-for="m in activeModels" :key="m.model_id" class="panel">
          <div class="panel-head">
            <h2 class="panel-title">{{ m.name }}</h2>
            <button type="button" class="ghost mini" @click="openClassModal(m.model_id)">
              类别 {{ (classFilter[m.model_id] ?? m.class_list.map((c) => c.class_name)).length }}/{{ m.class_list.length }}
            </button>
          </div>
        </section>

        <section class="panel grow">
          <div class="panel-head">
            <h2 class="panel-title">{{ t('workbench.results') }}（{{ objects.length }}）</h2>
          </div>
          <div class="panel-body results">
            <div
              v-for="o in resultItems"
              :key="o.id + '-' + o.model_id"
              class="result-item"
              :class="{ selected: selectedId === o.id }"
              @click="selectedId = o.id"
            >
              <span class="swatch" :style="{ background: o.style?.color || '#2F6FED' }" />
              <span>{{ o.id }}:{{ o.display }}</span>
              <span class="num conf">{{ o.confText }}</span>
              <button type="button" class="ghost mini" @click.stop="toggleVisible(o.id)">
                {{ o.visible === false ? '显示' : '隐藏' }}
              </button>
            </div>
            <div v-if="!objects.length" class="muted">{{ t('empty.noResult') }}</div>
          </div>
        </section>
      </div>
    </div>

    <div v-if="gallery.length" class="album-wrap">
      <div class="album-bar">
        <span class="muted">已选 {{ selectedGalleryPaths.size }}/{{ gallery.length }}</span>
        <button type="button" class="ghost mini" @click="selectAllGallery">全选</button>
        <button type="button" class="ghost mini" @click="clearGallerySelection">清空选择</button>
        <button
          type="button"
          class="primary mini"
          :disabled="running"
          @click="mediaKind === 'folder' ? runFolder(mediaPath, selectedGalleryPaths.size ? [...selectedGalleryPaths] : gallery.map((g) => g.path)) : startInfer()"
        >
          {{ t('action.startInfer') }}
        </button>
      </div>
      <div class="album">
        <div
          v-for="(g, i) in gallery"
          :key="g.path + i"
          class="album-item"
          :class="{
            active: i === currentGalleryIndex,
            processing: g.status === 'processing',
            checked: selectedGalleryPaths.has(g.path)
          }"
          @click="selectGallery(i)"
          @click.ctrl.prevent="toggleGallerySelect(g.path, $event)"
          @click.meta.prevent="toggleGallerySelect(g.path, $event)"
          @click.shift.prevent="toggleGallerySelect(g.path, $event)"
        >
          <div class="thumb-box">
            <img v-if="g.thumb || g.url" :src="g.thumb || g.url" :alt="g.name" />
            <div v-else class="ph">#{{ i + 1 }}</div>
            <div v-if="g.status === 'processing'" class="busy-mask"><span>识别中…</span></div>
            <div v-else-if="g.status === 'done' && (g.objects?.length || 0) > 0" class="done-badge">
              {{ g.objects?.length }}
            </div>
            <input
              class="pick"
              type="checkbox"
              :checked="selectedGalleryPaths.has(g.path)"
              @click.stop="toggleGallerySelect(g.path)"
            />
          </div>
          <div class="cap num">{{ g.name }}</div>
        </div>
      </div>
    </div>

    <ClassPickerModal
      :visible="!!classModalModelItem"
      :title="`${classModalModelItem?.name || ''} · 类别选择`"
      :classes="classModalModelItem?.class_list || []"
      :selected="classFilter[classModalModel] ?? (classModalModelItem?.class_list || []).map((c) => c.class_name)"
      @update:visible="(v) => { if (!v) classModalModel = '' }"
      @update:selected="(list) => onClassUpdate(classModalModel, list)"
    />

    <MoreSettingsModal
      v-model:visible="showMore"
      :conf="conf"
      :max-side="maxSide"
      :label-template="labelTemplate"
      @apply="(p) => { conf = p.conf; maxSide = p.maxSide; labelTemplate = p.labelTemplate }"
    />

    <LabelConfigModal
      v-model:visible="showLabelCfg"
      v-model:model-value="labelSettings"
      @apply="(s) => { labelSettings = s }"
    />

    <div v-if="dragging" class="drop-mask">释放以导入图片或文件夹</div>
  </div>
</template>

<style scoped>
.image-page {
  height: 100%;
}
.sub {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.path {
  flex: 1;
  min-width: 80px;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lbl {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
.num-input,
.text-input {
  height: 28px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-panel);
  color: var(--text-primary);
  padding: 0 8px;
  font-size: var(--text-sm);
  width: 72px;
}
.text-input {
  width: 140px;
}
.sel {
  height: 28px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-panel);
  color: var(--text-primary);
  padding: 0 8px;
  font-size: var(--text-sm);
}
.err-text {
  color: var(--danger);
  margin: 0;
  font-size: var(--text-sm);
}
.muted-line {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
.work-grid {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 12px;
  flex: 1;
  min-height: 360px;
}
.canvas-panel {
  display: flex;
  min-height: 360px;
}
.canvas-panel :deep(.canvas-wrap),
.canvas-panel :deep(.empty-state) {
  flex: 1;
}
.side {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}
.panel .panel-head {
  padding: 8px 12px;
}
.panel .panel-body {
  padding: 10px 12px;
}
.models {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.row {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: var(--text-sm);
}
.name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mini {
  padding: 2px 6px;
  font-size: 11px;
}
.grow {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.results {
  flex: 1;
  overflow: auto;
}
.result-item {
  display: grid;
  grid-template-columns: 12px 1fr 48px 48px;
  gap: 6px;
  align-items: center;
  padding: 5px 2px;
  cursor: pointer;
  font-size: var(--text-sm);
}
.result-item.selected {
  background: var(--bg-active);
  border-radius: 4px;
}
.swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}
.conf {
  text-align: right;
  color: var(--text-secondary);
}
.muted {
  color: var(--text-muted);
  font-size: var(--text-sm);
}
.album-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.album-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--text-sm);
}
.album {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 8px 0 4px;
}
.album-item {
  min-width: 88px;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-panel);
  cursor: pointer;
}
.album-item.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}
.album-item.checked {
  outline: 2px solid color-mix(in srgb, var(--accent) 55%, transparent);
}
.album-item img {
  width: 88px;
  height: 64px;
  object-fit: cover;
  display: block;
}
.thumb-box {
  position: relative;
  width: 88px;
  height: 64px;
  overflow: hidden;
  background: var(--bg-inset);
}
.pick {
  position: absolute;
  left: 4px;
  top: 4px;
  z-index: 2;
}
.mini {
  padding: 2px 8px;
  font-size: 11px;
}
.busy-mask {
  position: absolute;
  inset: 0;
  background: rgba(80, 90, 100, 0.55);
  color: #fff;
  display: grid;
  place-items: center;
  font-size: 11px;
}
.done-badge {
  position: absolute;
  right: 4px;
  bottom: 4px;
  background: var(--accent);
  color: #fff;
  font-size: 10px;
  border-radius: 999px;
  padding: 0 5px;
}
.ph {
  width: 88px;
  height: 64px;
  display: grid;
  place-items: center;
  color: var(--text-muted);
  background: var(--bg-inset);
  font-size: var(--text-sm);
}
.cap {
  padding: 4px;
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.drop-mask {
  position: fixed;
  inset: 0;
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  border: 3px dashed var(--accent);
  display: grid;
  place-items: center;
  font-size: var(--text-xl);
  z-index: 900;
  pointer-events: none;
}
.image-page.dragging {
  outline: none;
}
</style>
