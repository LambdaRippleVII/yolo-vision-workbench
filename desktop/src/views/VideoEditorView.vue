<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import CanvasStage, { type BoxObject } from '../components/CanvasStage.vue'
import ModelPicker from '../components/ModelPicker.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import EmptyState from '../components/EmptyState.vue'
import { wsClient } from '../api/ws'
import { formatError } from '../utils/errors'
import { t } from '../locales'

interface FrameItem {
  frame_id: number
  object_count: number
}

interface ModelItem {
  model_id: string
  name: string
  loaded: boolean
  weights_available?: boolean
  downloadable?: boolean
  runtime_available?: boolean
  class_list?: Array<{ class_id: number; class_name: string; display_name: string }>
}

const taskId = ref('')
const videoPath = ref('')
const videoUrl = ref('')
const videoPreviewState = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
const videoPreviewError = ref('')
const labelTemplate = ref('{id}:{class}')
const timeline = ref<FrameItem[]>([])
const currentFrameId = ref(0)
const imageUrl = ref('')
const objects = ref<BoxObject[]>([])
const selectedId = ref<number | null>(null)
const selectedFrames = ref<Set<number>>(new Set())
const errorMsg = ref('')
const infoMsg = ref('')
const loading = ref(false)
const hasEdits = ref(false)
const showExportConfirm = ref(false)
const dragging = ref(false)
const running = ref(false)
const models = ref<ModelItem[]>([])
const selectedModels = ref<string[]>([])
const downloadingModelId = ref('')
const skipFrame = ref(5)
const boxPersistence = ref(5)
/** timeline precision: 1 = every frame */
const timelineStep = ref(1)
const filmstrip = ref<HTMLElement | null>(null)
const thumbs = ref<Record<number, string>>({})
const hiddenClasses = ref<Set<string>>(new Set())
/** timeline UI mode: filmstrip thumbs vs PR-style track bar */
const timelineMode = ref<'filmstrip' | 'track'>('filmstrip')
const draggingPlayhead = ref(false)
let videoPreviewRequestId = 0
let videoSelectionId = 0
let videoPreviewTimer: number | undefined
let stopDownloadProgress: (() => void) | undefined
let stopTaskDone: (() => void) | undefined
let stopClientOpen: (() => void) | undefined

const filteredObjects = computed(() =>
  objects.value.filter((o) => !hiddenClasses.value.has(o.class_name))
)

const classOptions = computed(() => {
  const set = new Map<string, string>()
  for (const o of objects.value) {
    if (!set.has(o.class_name)) set.set(o.class_name, o.display_name || o.class_name)
  }
  return [...set.entries()].map(([class_name, display]) => ({ class_name, display }))
})

const trackMarkers = computed(() => timeline.value)

function toggleHideClass(class_name: string): void {
  const set = new Set(hiddenClasses.value)
  if (set.has(class_name)) set.delete(class_name)
  else set.add(class_name)
  hiddenClasses.value = set
}

function showAllClasses(): void {
  hiddenClasses.value = new Set()
}

const currentIndex = computed(() => {
  const i = timeline.value.findIndex((x) => x.frame_id === currentFrameId.value)
  return i < 0 ? 0 : i
})

const sampledTimeline = computed(() => {
  const step = Math.max(1, timelineStep.value)
  if (step === 1) return timeline.value
  return timeline.value.filter((_, i) => i % step === 0)
})

const timecode = computed(() => {
  if (!timeline.value.length) return videoPath.value ? '待推理' : '000 / 000'
  const total = timeline.value.length || 0
  const cur = currentIndex.value
  const fmt = (n: number) => String(n).padStart(3, '0')
  return `${fmt(cur)} / ${fmt(total)}`
})

function setErr(e: unknown): void {
  errorMsg.value = formatError(e)
}

function looksLikeVideo(p: string): boolean {
  return /\.(mp4|avi|mov|mkv|webm|m4v|flv|3gp)$/i.test(p)
}

async function loadModels(): Promise<void> {
  try {
    const resp = await wsClient.request('model.list', {})
    models.value = ((resp.data as { models?: ModelItem[] }).models ?? []) as ModelItem[]
    if (!selectedModels.value.length && models.value.length) {
      selectedModels.value = [models.value[0].model_id]
    }
  } catch (e) {
    const msg = formatError(e)
    if (!msg.includes('通信未就绪')) errorMsg.value = msg
  }
}

async function downloadModel(modelId: string): Promise<boolean> {
  if (downloadingModelId.value) return false
  const model = models.value.find((item) => item.model_id === modelId)
  if (!model) return false

  downloadingModelId.value = modelId
  errorMsg.value = ''
  infoMsg.value = `正在下载 ${model.name} 权重…`
  try {
    const resp = await wsClient.request('model.downloadBuiltin', { model_ids: [modelId] }, 10 * 60 * 1000)
    const results = (resp.data as {
      results?: Array<{ model_id: string; ok: boolean; error?: string }>
    }).results || []
    const result = results.find((item) => item.model_id === modelId)
    await loadModels()
    if (!result?.ok) {
      errorMsg.value = `模型权重下载失败：${result?.error || '后端没有返回下载结果'}`
      infoMsg.value = ''
      return false
    }
    infoMsg.value = `${model.name} 权重已下载，可以开始推理。`
    return true
  } catch (e) {
    setErr(e)
    infoMsg.value = ''
    return false
  } finally {
    downloadingModelId.value = ''
  }
}

async function pickVideo(): Promise<void> {
  const api = window.yoloStudio
  errorMsg.value = ''
  infoMsg.value = ''
  if (!api?.selectVideo) {
    errorMsg.value = '请在桌面端中选择视频'
    return
  }
  try {
    const path = await api.selectVideo()
    if (!path) return
    await setVideo(path)
  } catch (e) {
    setErr(e)
  }
}

async function setVideo(path: string): Promise<void> {
  videoSelectionId += 1
  videoPath.value = path
  videoUrl.value = ''
  imageUrl.value = ''
  objects.value = []
  timeline.value = []
  thumbs.value = {}
  currentFrameId.value = 0
  selectedId.value = null
  selectedFrames.value = new Set()
  taskId.value = ''
  loading.value = false
  hasEdits.value = false
  videoPreviewError.value = ''
  errorMsg.value = ''
  await loadVideoPreview(path)
}

function clearVideoPreviewTimer(): void {
  if (videoPreviewTimer !== undefined) {
    window.clearTimeout(videoPreviewTimer)
    videoPreviewTimer = undefined
  }
}

function previewErrorMessage(message: string): void {
  clearVideoPreviewTimer()
  videoPreviewState.value = 'error'
  videoPreviewError.value = message
  errorMsg.value = `视频预览失败：${message}。请检查文件是否损坏或转为 H.264 MP4；也可以点「开始推理」查看后端解码结果。`
  infoMsg.value = ''
}

async function loadVideoPreview(path: string): Promise<void> {
  const requestId = ++videoPreviewRequestId
  clearVideoPreviewTimer()
  videoPreviewState.value = 'loading'
  videoPreviewError.value = ''
  infoMsg.value = `已选择视频：${path.split(/[\\/]/).pop() || path}，正在读取视频信息…`

  try {
    const api = window.yoloStudio
    let baseUrl = 'http://127.0.0.1:8765'
    if (api?.getWsUrl) {
      const wsUrl = await api.getWsUrl()
      baseUrl = wsUrl.replace(/^wss:/i, 'https:').replace(/^ws:/i, 'http:').replace(/\/ws\/?$/i, '')
    }
    if (requestId !== videoPreviewRequestId) return
    videoUrl.value = `${baseUrl}/media?path=${encodeURIComponent(path)}`
    videoPreviewTimer = window.setTimeout(() => {
      if (requestId === videoPreviewRequestId && videoPreviewState.value === 'loading') {
        previewErrorMessage('等待视频元数据超时；请检查后端连接、文件权限和视频编码格式')
      }
    }, 15_000)
  } catch (e) {
    if (requestId === videoPreviewRequestId) previewErrorMessage(formatError(e))
  }
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '时长未知'
  const total = Math.floor(seconds)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const remaining = total % 60
  return hours
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`
    : `${minutes}:${String(remaining).padStart(2, '0')}`
}

function onVideoLoadedMetadata(ev: Event): void {
  const video = ev.currentTarget as HTMLVideoElement
  if (video.getAttribute('src') !== videoUrl.value) return
  if (!video.videoWidth || !video.videoHeight) {
    previewErrorMessage('视频没有有效画面信息，文件可能损坏')
    return
  }
  clearVideoPreviewTimer()
  videoPreviewState.value = 'ready'
  videoPreviewError.value = ''
  errorMsg.value = ''
  infoMsg.value = `视频已加载：${video.videoWidth}×${video.videoHeight} · ${formatDuration(video.duration)}`
}

function onVideoError(ev: Event): void {
  const video = ev.currentTarget as HTMLVideoElement
  if (video.getAttribute('src') !== videoUrl.value) return
  const code = video.error?.code
  const message = video.error?.message?.trim()
  const reasons: Record<number, string> = {
    1: '读取已中止',
    2: '无法读取视频文件，请检查文件是否存在、可访问',
    3: '视频解码失败，文件可能损坏或编码不受支持',
    4: '浏览器不支持此视频格式或编码，建议转为 H.264 MP4'
  }
  const reason = (code && reasons[code]) || '播放器无法加载此视频'
  previewErrorMessage(message ? `${reason}（${message}）` : reason)
}

async function startDetect(): Promise<void> {
  if (!videoPath.value) {
    errorMsg.value = '请先选择视频'
    return
  }
  if (!selectedModels.value.length) {
    errorMsg.value = t('workbench.noModel')
    return
  }
  running.value = true
  errorMsg.value = ''
  try {
    for (const modelId of selectedModels.value) {
      let model = models.value.find((item) => item.model_id === modelId)
      if (!model) continue
      if (model.runtime_available === false) {
        throw new Error('当前安装包缺少 YOLO 推理组件，请安装包含 CPU 推理环境的新版安装包。')
      }
      if (model.weights_available === false) {
        if (!model.downloadable) {
          throw new Error(`模型「${model.name}」缺少权重文件，请先在模型管理中导入对应权重。`)
        }
        const downloaded = await downloadModel(modelId)
        if (!downloaded) return
        model = models.value.find((item) => item.model_id === modelId)
        if (model?.weights_available === false) {
          throw new Error(`模型「${model.name}」权重仍不可用，请到模型管理检查下载结果。`)
        }
      }
    }

    const resp = await wsClient.request('video.start', {
      media_path: videoPath.value,
      model_ids: selectedModels.value,
      skip_frame: skipFrame.value,
      box_persistence: Math.min(boxPersistence.value, skipFrame.value)
    })
    const task = (resp.data as { task?: { task_id?: string } }).task
    taskId.value = task?.task_id || ''
    infoMsg.value = '视频检测中…'
  } catch (e) {
    setErr(e)
  } finally {
    running.value = false
  }
}

async function loadTimeline(): Promise<void> {
  if (!taskId.value) return
  const selectionId = videoSelectionId
  const requestedTaskId = taskId.value
  try {
    const resp = await wsClient.request('result.frames', { task_id: requestedTaskId })
    if (selectionId !== videoSelectionId || requestedTaskId !== taskId.value) return
    timeline.value = ((resp.data as { frames?: FrameItem[] }).frames ?? []) as FrameItem[]
    if (timeline.value.length) {
      await showFrame(timeline.value[0].frame_id)
      void loadThumbs()
    }
  } catch (e) {
    if (selectionId === videoSelectionId && requestedTaskId === taskId.value) setErr(e)
  }
}

async function loadThumbs(): Promise<void> {
  if (!videoPath.value || !timeline.value.length) return
  const selectionId = videoSelectionId
  const requestedTaskId = taskId.value
  const requestedVideoPath = videoPath.value
  const ids = sampledTimeline.value.map((f) => f.frame_id).slice(0, 120)
  if (!ids.length) return
  try {
    const resp = await wsClient.request('result.thumbs', {
      video_path: requestedVideoPath,
      frame_ids: ids
    })
    if (selectionId !== videoSelectionId || requestedTaskId !== taskId.value) return
    const list = ((resp.data as { thumbs?: Array<{ frame_id: number; thumb_url: string }> }).thumbs || []) as Array<{
      frame_id: number
      thumb_url: string
    }>
    const map: Record<number, string> = { ...thumbs.value }
    for (const t of list) {
      if (t.thumb_url) map[t.frame_id] = t.thumb_url
    }
    thumbs.value = map
  } catch {
    /* thumbs optional */
  }
}

async function showFrame(frameId: number): Promise<void> {
  const selectionId = videoSelectionId
  const requestedTaskId = taskId.value
  const requestedVideoPath = videoPath.value
  currentFrameId.value = frameId
  loading.value = true
  try {
    if (requestedVideoPath) {
      const preview = await wsClient.request('result.preview', {
        video_path: requestedVideoPath,
        frame_id: frameId
      })
      if (selectionId !== videoSelectionId || requestedTaskId !== taskId.value) return
      imageUrl.value = String((preview.data as { data_url?: string }).data_url || '')
    }
    const frameResp = await wsClient.request('result.frame', {
      task_id: requestedTaskId,
      frame_id: frameId
    })
    if (selectionId !== videoSelectionId || requestedTaskId !== taskId.value) return
    objects.value = ((frameResp.data as { objects?: BoxObject[] }).objects ?? []) as BoxObject[]
    selectedId.value = objects.value.length ? objects.value[0].id : null
  } catch (e) {
    if (selectionId === videoSelectionId && requestedTaskId === taskId.value) setErr(e)
  } finally {
    if (selectionId === videoSelectionId && requestedTaskId === taskId.value) loading.value = false
  }
}

function stepFrame(delta: number): void {
  const next = Math.min(timeline.value.length - 1, Math.max(0, currentIndex.value + delta))
  const item = timeline.value[next]
  if (item) void showFrame(item.frame_id)
}

function playheadLeft(): string {
  const step = Math.max(1, timelineStep.value)
  const idx = Math.floor(currentIndex.value / step)
  return `calc(${idx} * 55px + 26px)`
}

function trackPlayheadLeft(): string {
  const n = Math.max(1, timeline.value.length - 1)
  return `${(currentIndex.value / n) * 100}%`
}

function seekByRatio(ratio: number): void {
  if (!timeline.value.length) return
  const idx = Math.min(timeline.value.length - 1, Math.max(0, Math.round(ratio * (timeline.value.length - 1))))
  const item = timeline.value[idx]
  if (item) void showFrame(item.frame_id)
}

function onTrackScrub(ev: MouseEvent): void {
  const el = ev.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  seekByRatio((ev.clientX - rect.left) / rect.width)
}

function onStartPlayheadDrag(ev: MouseEvent): void {
  ev.preventDefault()
  ev.stopPropagation()
  draggingPlayhead.value = true
  const onMove = (e: MouseEvent) => {
    const parent = (ev.currentTarget as HTMLElement).parentElement
    if (!parent) return
    const rect = parent.getBoundingClientRect()
    seekByRatio((e.clientX - rect.left) / rect.width)
  }
  const onUp = () => {
    draggingPlayhead.value = false
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

function onFilmScrub(ev: MouseEvent): void {
  const el = filmstrip.value
  if (!el || !sampledTimeline.value.length) return
  const rect = el.getBoundingClientRect()
  const ratio = Math.min(1, Math.max(0, (ev.clientX - rect.left) / rect.width))
  const idx = Math.round(ratio * (sampledTimeline.value.length - 1))
  const item = sampledTimeline.value[idx]
  if (item) void showFrame(item.frame_id)
}

function toggleFrameSelect(frameId: number, ev: MouseEvent): void {
  const set = new Set(selectedFrames.value)
  if (ev.shiftKey && selectedFrames.value.size) {
    const a = timeline.value.findIndex((x) => x.frame_id === currentFrameId.value)
    const b = timeline.value.findIndex((x) => x.frame_id === frameId)
    const lo = Math.min(a, b)
    const hi = Math.max(a, b)
    for (let i = lo; i <= hi; i++) {
      const id = timeline.value[i]?.frame_id
      if (id !== undefined) set.add(id)
    }
  } else if (set.has(frameId)) {
    set.delete(frameId)
  } else {
    set.add(frameId)
  }
  selectedFrames.value = set
}

function selectAllFrames(): void {
  selectedFrames.value = new Set(timeline.value.map((x) => x.frame_id))
}

function clearFrameSelection(): void {
  selectedFrames.value = new Set()
}

async function toggleVisible(id: number): Promise<void> {
  const o = objects.value.find((x) => x.id === id)
  if (!o || !taskId.value) return
  const next = o.visible === false
  o.visible = next
  hasEdits.value = true
  try {
    await wsClient.request('ops.setVisible', {
      task_id: taskId.value,
      frame_id: currentFrameId.value,
      object_id: id,
      model_id: o.model_id,
      visible: next
    })
  } catch (e) {
    setErr(e)
  }
}

async function saveSelectedFrames(): Promise<void> {
  const api = window.yoloStudio
  if (!selectedFrames.value.size) {
    errorMsg.value = '请先在时间轴多选帧（Shift 连选）'
    return
  }
  if (!videoPath.value) return
  let outDir = ''
  if (api?.selectFolder) {
    outDir = (await api.selectFolder()) || ''
    if (!outDir) return
  }
  try {
    const resp = await wsClient.request('export.frames', {
      task_id: taskId.value,
      video_path: videoPath.value,
      output_dir: outDir,
      frame_ids: [...selectedFrames.value],
      label_template: labelTemplate.value
    })
    infoMsg.value = `已保存 ${((resp.data as { count?: number }).count ?? 0)} 帧`
  } catch (e) {
    setErr(e)
  }
}

async function doExportVideo(): Promise<void> {
  const api = window.yoloStudio
  if (!videoPath.value) return
  let outPath = ''
  if (api?.saveVideo) {
    outPath = (await api.saveVideo('识别结果.mp4')) || ''
    if (!outPath) return
  }
  try {
    await wsClient.request('export.video', {
      source_video: videoPath.value,
      output_path: outPath,
      source_task_id: taskId.value,
      label_template: labelTemplate.value,
      hidden_classes: [...hiddenClasses.value]
    })
    infoMsg.value = '视频导出任务已提交，请稍候'
  } catch (e) {
    setErr(e)
  }
}

function requestExportVideo(): void {
  if (hasEdits.value) {
    showExportConfirm.value = true
    return
  }
  void doExportVideo()
}

function resolveDropPath(file: File): string {
  const api = window.yoloStudio
  if (api?.getPathForFile) return api.getPathForFile(file) || ''
  return (file as File & { path?: string }).path || ''
}

async function handleDrop(ev: DragEvent): Promise<void> {
  ev.preventDefault()
  ev.stopPropagation()
  dragging.value = false
  const files = ev.dataTransfer?.files
  if (!files?.length) return
  for (const f of Array.from(files)) {
    const p = resolveDropPath(f)
    if (p && looksLikeVideo(p)) {
      await setVideo(p)
      return
    }
  }
  errorMsg.value = '没有导入视频：请拖入 mp4/m4v/mov/avi/mkv/webm/flv/3gp 文件，并确认文件路径可访问。'
}

function clearDrag(): void {
  dragging.value = false
}

async function handlePaste(ev: ClipboardEvent): Promise<void> {
  const items = ev.clipboardData?.files
  if (!items?.length) return
  const f = items[0]
  const p = resolveDropPath(f)
  if (p && looksLikeVideo(p)) await setVideo(p)
  else errorMsg.value = '无法从剪贴板读取视频路径，请使用「选择视频」或直接拖入视频文件。'
}

async function openFromRoute(): Promise<void> {
  const hash = window.location.hash
  const q = hash.includes('?') ? hash.split('?')[1] : ''
  const params = new URLSearchParams(q || '')
  taskId.value = params.get('task') || sessionStorage.getItem('editor_task_id') || taskId.value
  videoPath.value = params.get('video') || sessionStorage.getItem('editor_video_path') || videoPath.value
  if (videoPath.value) {
    void loadVideoPreview(videoPath.value)
  }
  if (taskId.value) void loadTimeline()
}

watch(timelineStep, () => {
  void loadThumbs()
})

function onWindowDragEnter(ev: DragEvent): void {
  ev.preventDefault()
  if (ev.dataTransfer?.types?.includes('Files')) dragging.value = true
}

function onWindowDragOver(ev: DragEvent): void {
  ev.preventDefault()
  if (ev.dataTransfer?.types?.includes('Files')) dragging.value = true
}

function onWindowDragLeave(ev: DragEvent): void {
  if (ev.relatedTarget === null) dragging.value = false
}

function onWindowDrop(ev: DragEvent): void {
  ev.preventDefault()
  void handleDrop(ev)
}

function onWindowPaste(ev: ClipboardEvent): void {
  void handlePaste(ev)
}

onMounted(() => {
  void openFromRoute()
  void loadModels()
  stopClientOpen = wsClient.on('client.open', () => {
    if (errorMsg.value.includes('通信未就绪')) errorMsg.value = ''
    void loadModels()
    if (taskId.value) void loadTimeline()
  })
  window.addEventListener('dragenter', onWindowDragEnter)
  window.addEventListener('dragover', onWindowDragOver)
  window.addEventListener('dragleave', onWindowDragLeave)
  window.addEventListener('dragend', clearDrag)
  window.addEventListener('drop', onWindowDrop)
  window.addEventListener('paste', onWindowPaste)
  stopDownloadProgress = wsClient.on('model.download.progress', (msg) => {
    const data = msg.data as { model_id?: string; message?: string } | undefined
    if (data?.model_id === downloadingModelId.value && data.message) infoMsg.value = data.message
  })
  stopTaskDone = wsClient.on('task.done', (msg: { data?: Record<string, unknown> }) => {
    const d = msg.data || {}
    if (d.type === 'video' && d.status === 'completed') {
      infoMsg.value = '视频检测完成'
      void loadTimeline()
    }
    if (d.type === 'video' && d.status === 'failed') {
      errorMsg.value = String(d.error || '视频检测失败')
    }
  })
})
onUnmounted(() => {
  dragging.value = false
  videoPreviewRequestId += 1
  clearVideoPreviewTimer()
  window.removeEventListener('dragenter', onWindowDragEnter)
  window.removeEventListener('dragover', onWindowDragOver)
  window.removeEventListener('dragleave', onWindowDragLeave)
  window.removeEventListener('dragend', clearDrag)
  window.removeEventListener('drop', onWindowDrop)
  window.removeEventListener('paste', onWindowPaste)
  stopDownloadProgress?.()
  stopTaskDone?.()
  stopClientOpen?.()
})
</script>

<template>
  <div class="editor" :class="{ dragging }">
    <!-- top command bar -->
    <header class="cmd-bar">
      <div class="cmd-left">
        <button type="button" class="primary" @click="pickVideo">{{ t('action.selectVideo') }}</button>
        <button
          type="button"
          class="primary"
          :disabled="running || Boolean(downloadingModelId) || !videoPath || !selectedModels.length"
          @click="startDetect"
        >
          {{ running ? t('status.running') : t('action.startInfer') }}
        </button>
        <button type="button" :disabled="!taskId" @click="requestExportVideo">
          {{ t('editor.exportVideo') }}
        </button>
        <button type="button" :disabled="!selectedFrames.size" @click="saveSelectedFrames">
          {{ t('editor.saveFrames') }}
        </button>
      </div>
      <div class="cmd-path num">{{ videoPath || '拖入 / Ctrl+V / 选择视频' }}</div>
      <div class="cmd-right">
        <span class="tc num">{{ timecode }}</span>
      </div>
    </header>

    <!-- main 3 columns -->
    <div class="work">
      <aside class="side left">
        <section class="panel">
          <div class="panel-head"><h3>模型</h3></div>
          <div class="panel-body">
            <ModelPicker
              v-model:selected="selectedModels"
              :models="models"
              :downloading-model-id="running ? 'busy' : downloadingModelId"
              compact
              @download="downloadModel"
            />
          </div>
        </section>
        <section class="panel">
          <div class="panel-head"><h3>参数</h3></div>
          <div class="panel-body params">
            <label>{{ t('workbench.skipFrame') }}</label>
            <input v-model.number="skipFrame" type="number" min="1" class="num" />
            <label>{{ t('workbench.boxPersistence') }}</label>
            <input v-model.number="boxPersistence" type="number" min="1" class="num" />
            <label>标签模板</label>
            <input v-model="labelTemplate" class="text" />
          </div>
        </section>
      </aside>

      <section class="monitor">
        <div class="monitor-stage">
          <CanvasStage
            v-if="imageUrl"
            :image-url="imageUrl"
            :objects="filteredObjects"
            :selected-id="selectedId"
            :label-template="labelTemplate"
            @select="(id) => (selectedId = id)"
          />
          <video
            v-else-if="videoUrl"
            :key="videoUrl"
            class="video-preview"
            :src="videoUrl"
            preload="metadata"
            controls
            muted
            @loadedmetadata="onVideoLoadedMetadata"
            @error="onVideoError"
          />
          <div v-else-if="videoPath" class="video-placeholder">
            <span v-if="videoPreviewState === 'loading'">正在读取视频信息…</span>
            <span v-else-if="videoPreviewError">{{ videoPreviewError }}</span>
          </div>
          <EmptyState v-else icon="▶" :title="t('editor.title')" :description="t('editor.empty')" />
          <div v-if="videoPreviewError && videoUrl" class="video-preview-error" role="alert">
            <strong>视频预览失败</strong>
            <span>{{ videoPreviewError }}</span>
            <small>可尝试转为 H.264 MP4；也可以点击「开始推理」查看后端是否能解码。</small>
          </div>
        </div>
      </section>

      <aside class="side right">
        <section class="panel grow">
          <div class="panel-head">
            <h3>{{ t('workbench.results') }}（{{ filteredObjects.length }}）</h3>
          </div>
          <div class="panel-body results">
            <div class="class-hide">
              <span class="lbl">类别显隐</span>
              <button
                v-for="c in classOptions"
                :key="c.class_name"
                type="button"
                class="ghost mini"
                :class="{ off: hiddenClasses.has(c.class_name) }"
                @click="toggleHideClass(c.class_name)"
              >
                {{ c.display }}
              </button>
              <button v-if="hiddenClasses.size" type="button" class="ghost mini" @click="showAllClasses">
                全部显示
              </button>
            </div>
            <div
              v-for="o in filteredObjects"
              :key="o.id + '-' + o.model_id"
              class="result-item"
              :class="{ selected: selectedId === o.id }"
              @click="selectedId = o.id"
            >
              <span class="swatch" :style="{ background: o.style?.color || '#2F6FED' }" />
              <span>{{ o.id }}:{{ o.display_name || o.class_name }}</span>
              <button type="button" class="ghost mini" @click.stop="toggleVisible(o.id)">
                {{ o.visible === false ? '显示' : '隐藏' }}
              </button>
            </div>
            <div v-if="!filteredObjects.length" class="muted">{{ t('empty.noResult') }}</div>
          </div>
        </section>
      </aside>
    </div>

    <!-- PR-style timeline -->
    <footer class="timeline-panel">
      <div class="tl-toolbar">
        <button type="button" class="ghost mini" :disabled="currentIndex <= 0" @click="stepFrame(-1)">◀</button>
        <button
          type="button"
          class="ghost mini"
          :disabled="currentIndex >= timeline.length - 1"
          @click="stepFrame(1)"
        >
          ▶
        </button>
        <button type="button" class="ghost mini" @click="selectAllFrames">全选帧</button>
        <button type="button" class="ghost mini" @click="clearFrameSelection">
          清空（{{ selectedFrames.size }}）
        </button>
        <div class="tl-zoom">
          <span class="lbl">视图</span>
          <button
            type="button"
            class="ghost mini"
            :class="{ on: timelineMode === 'track' }"
            @click="timelineMode = 'track'"
          >
            时间轨
          </button>
          <button
            type="button"
            class="ghost mini"
            :class="{ on: timelineMode === 'filmstrip' }"
            @click="timelineMode = 'filmstrip'"
          >
            缩略胶片
          </button>
          <template v-if="timelineMode === 'filmstrip'">
            <span class="lbl">精度</span>
            <input
              v-model.number="timelineStep"
              type="range"
              min="1"
              max="30"
              step="1"
              class="range"
            />
            <span class="num muted">{{ timelineStep === 1 ? '每帧' : `每 ${timelineStep} 帧` }}</span>
          </template>
        </div>
        <div class="tl-info num">
          <template v-if="timeline.length">
            帧 {{ currentFrameId }} · {{ timeline.length }} 帧
            <template v-if="loading"> · 加载中…</template>
          </template>
          <template v-else-if="videoPath">视频已导入 · 开始推理后生成帧结果</template>
          <template v-else>等待视频</template>
        </div>
      </div>

      <div class="tl-ruler num">
        <span>0</span>
        <span>{{ Math.floor((timeline.length || 0) / 2) }}</span>
        <span>{{ timeline.length }}</span>
      </div>

      <!-- PR-style single track bar -->
      <div
        v-if="timelineMode === 'track' && timeline.length"
        class="track-bar"
        @mousedown="onTrackScrub"
        @mousemove="($event.buttons === 1 ? onTrackScrub($event) : undefined)"
      >
        <div class="track-fill" />
        <div
          class="track-playhead"
          :class="{ dragging: draggingPlayhead }"
          :style="{ left: trackPlayheadLeft() }"
          @mousedown="onStartPlayheadDrag"
        >
          <div class="track-head" />
        </div>
        <div class="track-marks">
          <span
            v-for="m in trackMarkers"
            :key="m.frame_id"
            class="track-mark"
            :class="{ hidden: !m.object_count }"
            :style="{ left: `${(m.frame_id / Math.max(1, timeline.length - 1)) * 100}%` }"
            :title="`#${m.frame_id}`"
          />
        </div>
      </div>

      <!-- filmstrip mode -->
      <div
        v-if="timelineMode === 'filmstrip'"
        ref="filmstrip"
        class="filmstrip"
        @mousedown.self="onFilmScrub"
        @mousemove="($event.buttons === 1 ? onFilmScrub($event) : undefined)"
      >
        <div class="playhead" :style="{ left: playheadLeft() }" />
        <button
          v-for="f in sampledTimeline"
          :key="f.frame_id"
          type="button"
          class="cell"
          :class="{
            active: f.frame_id === currentFrameId,
            selected: selectedFrames.has(f.frame_id)
          }"
          @click="showFrame(f.frame_id)"
          @click.ctrl.prevent="toggleFrameSelect(f.frame_id, $event)"
          @click.meta.prevent="toggleFrameSelect(f.frame_id, $event)"
          @click.shift.prevent="toggleFrameSelect(f.frame_id, $event)"
        >
          <img v-if="thumbs[f.frame_id]" :src="thumbs[f.frame_id]" class="thumb-img" :alt="String(f.frame_id)" />
          <div v-else class="thumb-ph">#{{ f.frame_id }}</div>
          <span class="cnt">{{ f.object_count }}</span>
        </button>
      </div>
    </footer>

    <p v-if="errorMsg" class="err-text">{{ errorMsg }}</p>
    <p v-if="infoMsg" class="info-text">{{ infoMsg }}</p>

    <ConfirmDialog
      :visible="showExportConfirm"
      :title="t('editor.exportConfirmTitle')"
      :message="t('editor.exportConfirmMsg')"
      :confirm-text="t('editor.exportVideo')"
      @confirm="() => { showExportConfirm = false; doExportVideo() }"
      @cancel="showExportConfirm = false"
    />
    <div v-if="dragging" class="drop-mask" @dragleave="clearDrag" @drop="handleDrop">
      释放以导入视频
    </div>
  </div>
</template>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--bg-workspace);
}
.cmd-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border);
  flex: 0 0 auto;
}
.cmd-left {
  display: flex;
  gap: 8px;
}
.cmd-path {
  flex: 1;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  opacity: 0.85;
}
.tc {
  font-size: 13px;
  font-weight: 600;
  background: var(--bg-inset);
  padding: 4px 10px;
  border-radius: 6px;
}
.work {
  display: grid;
  grid-template-columns: 240px 1fr 260px;
  gap: 10px;
  padding: 10px 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.side {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow: hidden;
}
.panel {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.panel-head {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-inset);
  flex: 0 0 auto;
}
.panel-head h3 {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: 600;
}
.panel-body {
  padding: 10px;
  overflow: auto;
  min-height: 0;
}
.side > .panel:nth-child(1) {
  flex: 1 1 55%;
}
.side > .panel:nth-child(2) {
  flex: 0 0 auto;
  max-height: 45%;
}
.params {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px;
  align-items: center;
  font-size: var(--text-sm);
}
.params .num,
.params .text {
  height: 28px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0 8px;
  background: var(--bg-inset);
  color: var(--text-primary);
  min-width: 0;
  width: 100%;
}
.monitor {
  min-width: 0;
  min-height: 0;
  display: flex;
  background: var(--bg-canvas);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
.monitor-stage {
  flex: 1;
  display: flex;
  min-height: 280px;
  position: relative;
}
.monitor-stage :deep(.canvas-wrap),
.monitor-stage :deep(.empty-state),
.monitor-stage :deep(.video-preview) {
  flex: 1;
}
.video-preview {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: var(--bg-canvas);
}
.video-placeholder {
  flex: 1;
  display: grid;
  place-items: center;
  padding: 24px;
  color: var(--text-secondary);
  text-align: center;
  background: var(--bg-canvas);
}
.video-preview-error {
  position: absolute;
  z-index: 2;
  top: 12px;
  left: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, var(--danger) 35%, transparent);
  border-radius: 8px;
  color: var(--danger);
  background: color-mix(in srgb, var(--bg-panel) 94%, var(--danger));
  font-size: var(--text-sm);
}
.video-preview-error small {
  color: var(--text-secondary);
}
.grow {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.results {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.result-item {
  display: grid;
  grid-template-columns: 12px 1fr auto;
  gap: 6px;
  align-items: center;
  padding: 6px 4px;
  cursor: pointer;
  font-size: var(--text-sm);
  border-radius: 6px;
}
.result-item.selected {
  background: var(--bg-active);
}
.swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}
.mini {
  padding: 2px 6px;
  font-size: 11px;
}

/* timeline */
.timeline-panel {
  flex: 0 0 150px;
  background: var(--bg-panel);
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.tl-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
}
.tl-zoom {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: 8px;
  flex-wrap: wrap;
}
.tl-zoom .on {
  background: var(--accent-soft);
  color: var(--accent);
}
.range {
  width: 120px;
  accent-color: var(--accent);
}
.track-bar {
  position: relative;
  margin: 10px 12px;
  height: 56px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-inset);
  cursor: ew-resize;
  overflow: hidden;
}
.track-fill {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, color-mix(in srgb, var(--accent) 8%, transparent), transparent);
}
.track-marks {
  position: absolute;
  left: 0;
  right: 0;
  top: 18px;
  height: 16px;
}
.track-mark {
  position: absolute;
  width: 2px;
  height: 16px;
  background: var(--accent);
  opacity: 0.75;
  transform: translateX(-1px);
}
.track-mark.hidden {
  opacity: 0.25;
}
.track-playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--danger);
  z-index: 4;
  transform: translateX(-1px);
}
.track-playhead .track-head {
  position: absolute;
  top: 0;
  left: -5px;
  width: 12px;
  height: 10px;
  background: var(--danger);
  border-radius: 2px 2px 6px 6px;
  cursor: grab;
}
.track-playhead.dragging .track-head {
  cursor: grabbing;
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
  pointer-events: auto;
}
.tl-info {
  margin-left: auto;
  color: var(--text-secondary);
  font-size: 12px;
}
.tl-ruler {
  display: flex;
  justify-content: space-between;
  padding: 2px 10px;
  font-size: 10px;
  color: var(--text-muted);
  border-bottom: 1px solid color-mix(in srgb, var(--border) 50%, transparent);
}
.filmstrip {
  position: relative;
  display: flex;
  gap: 3px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 8px 10px;
  flex: 1;
  cursor: ew-resize;
  background: repeating-linear-gradient(
    90deg,
    var(--bg-inset),
    var(--bg-inset) 1px,
    transparent 1px,
    transparent 24px
  );
}
.playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--danger);
  z-index: 3;
  pointer-events: none;
  box-shadow: 0 0 4px rgba(214, 69, 69, 0.5);
}
.cell {
  flex: 0 0 52px;
  height: 100%;
  min-height: 72px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-panel);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 10px;
  padding: 2px;
  overflow: hidden;
}
.thumb-img {
  width: 100%;
  height: 52px;
  object-fit: cover;
  border-radius: 2px;
  display: block;
}
.thumb-ph {
  height: 52px;
  display: grid;
  place-items: center;
  background: var(--bg-inset);
  color: var(--text-muted);
}
.class-hide {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}
.class-hide .off {
  opacity: 0.45;
  text-decoration: line-through;
}
.cell.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.cell.selected {
  box-shadow: inset 0 0 0 2px var(--accent);
}
.cnt {
  color: var(--text-muted);
  align-self: flex-end;
}
.err-text {
  margin: 0 12px 6px;
  color: var(--danger);
  font-size: var(--text-sm);
}
.info-text {
  margin: 0 12px 6px;
  color: var(--text-secondary);
  font-size: var(--text-sm);
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
.muted {
  color: var(--text-muted);
  font-size: var(--text-sm);
}
.lbl {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
</style>
