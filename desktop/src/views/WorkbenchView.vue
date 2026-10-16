<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import EmptyState from '../components/EmptyState.vue'
import CanvasStage, { type BoxObject } from '../components/CanvasStage.vue'
import { DEFAULT_BOX_COLOR } from '../components/labelTypes'
import { wsClient } from '../api/ws'
import { formatError } from '../utils/errors'
import { t } from '../locales'

interface ModelItem {
  model_id: string
  name: string
  loaded: boolean
  class_list: Array<{ class_name: string; display_name: string }>
}

interface ProfileItem {
  profile_id: string
  name: string
  payload: {
    models?: Array<{ model_id: string; enabled: boolean; conf?: number }>
    render?: { label_template?: string }
    runtime?: { skip_frame?: number; box_persistence?: number }
  }
}

const mode = ref<'image' | 'video' | 'camera'>('image')
const mediaPath = ref('')
const imageUrl = ref('')
const videoUrl = ref('')
const objects = ref<BoxObject[]>([])
const selectedId = ref<number | null>(null)
const models = ref<ModelItem[]>([])
const selectedModels = ref<string[]>([])
const conf = ref(0.45)
const labelTemplate = ref('{id}:{class}')
const running = ref(false)
const errorMsg = ref('')
const lastMeta = ref<Record<string, unknown> | null>(null)
const folderPath = ref('')
const progressText = ref('')
const lastVideoTaskId = ref('')
const lastImageTaskId = ref('')
const lastVideoSummary = ref<Record<string, unknown> | null>(null)
const timeline = ref<Array<{ frame_id: number; object_count: number; is_detect?: boolean }>>([])
const currentFrameId = ref(0)
const loadingFrame = ref(false)
const camSourceType = ref<'usb' | 'rtsp'>('usb')
const camDeviceIndex = ref(0)
const camRtspUrl = ref('')
const camStreamId = ref('')
const camLive = ref(false)
const camFrameCount = ref(0)
const camDetectCount = ref(0)

const profiles = ref<ProfileItem[]>([])
const activeProfileId = ref('default')
const profileName = ref('默认配置')
const skipFrame = ref(5)
const boxPersistence = ref(5)

const resultItems = computed(() =>
  objects.value.map((o) => ({
    ...o,
    display: `${o.display_name || o.class_name}`,
    confText: `${Math.round(o.confidence * 100)}%`
  }))
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

async function loadProfiles(): Promise<void> {
  try {
    const resp = await wsClient.request('profile.list', {})
    profiles.value = ((resp.data as { profiles?: ProfileItem[] }).profiles ?? []) as ProfileItem[]
    if (!activeProfileId.value && profiles.value.length) {
      activeProfileId.value = profiles.value[0].profile_id
    }
  } catch (e) {
    const msg = formatError(e)
    if (!msg.includes('通信未就绪')) errorMsg.value = msg
  }
}

function buildPayload() {
  return {
    models: selectedModels.value.map((id) => ({ model_id: id, enabled: true, conf: conf.value })),
    pipeline: { mode: 'parallel', merge: 'concat' },
    runtime: {
      device: 'cpu',
      skip_frame: skipFrame.value,
      box_persistence: boxPersistence.value
    },
    render: {
      label_template: labelTemplate.value,
      default_color: DEFAULT_BOX_COLOR,
      line_width: 2,
      show_confidence: true
    }
  }
}

async function saveProfile(): Promise<void> {
  try {
    const resp = await wsClient.request('profile.save', {
      profile_id: activeProfileId.value || undefined,
      name: profileName.value || '未命名配置',
      payload: buildPayload()
    })
    const item = (resp.data as { profile?: ProfileItem }).profile
    if (item) {
      activeProfileId.value = item.profile_id
      profileName.value = item.name
    }
    await loadProfiles()
  } catch (e) {
    setErr(e)
  }
}

async function applyProfile(id: string): Promise<void> {
  activeProfileId.value = id
  try {
    const resp = await wsClient.request('profile.apply', { profile_id: id })
    const item = (resp.data as { profile?: ProfileItem }).profile
    if (!item) return
    profileName.value = item.name
    const payload = item.payload || {}
    const bound = (payload.models || []).filter((m) => m.enabled !== false).map((m) => m.model_id)
    if (bound.length) selectedModels.value = bound
    const firstConf = (payload.models || []).find((m) => typeof m.conf === 'number')
    if (firstConf && typeof firstConf.conf === 'number') conf.value = firstConf.conf
    if (payload.render?.label_template) labelTemplate.value = payload.render.label_template
    if (payload.runtime?.skip_frame) skipFrame.value = payload.runtime.skip_frame
    if (payload.runtime?.box_persistence) boxPersistence.value = payload.runtime.box_persistence
  } catch (e) {
    setErr(e)
  }
}

async function pickImage(): Promise<void> {
  const api = window.yoloStudio
  errorMsg.value = ''
  if (api?.selectImage) {
    const path = await api.selectImage()
    if (!path) return
    mediaPath.value = path
    folderPath.value = ''
    videoUrl.value = ''
    if (api.readImageBase64) {
      imageUrl.value = (await api.readImageBase64(path)) || ''
    }
  } else {
    errorMsg.value = '请在桌面端中选择图片'
    return
  }
  objects.value = []
  selectedId.value = null
}

async function pickVideo(): Promise<void> {
  const api = window.yoloStudio
  errorMsg.value = ''
  if (api?.selectVideo) {
    const path = await api.selectVideo()
    if (!path) return
    mediaPath.value = path
    folderPath.value = ''
    imageUrl.value = ''
    videoUrl.value = 'file:///' + path.replace(/\\/g, '/')
  } else {
    errorMsg.value = '请在桌面端中选择视频'
    return
  }
  objects.value = []
  selectedId.value = null
  timeline.value = []
}

async function pickFolder(): Promise<void> {
  const api = window.yoloStudio
  errorMsg.value = ''
  if (api?.selectFolder) {
    const path = await api.selectFolder()
    if (!path) return
    folderPath.value = path
    mediaPath.value = path
  } else {
    errorMsg.value = '请在桌面端中选择文件夹'
    return
  }
  objects.value = []
  selectedId.value = null
}

async function loadTimeline(taskId: string): Promise<void> {
  try {
    const resp = await wsClient.request('result.frames', { task_id: taskId })
    timeline.value = ((resp.data as { frames?: typeof timeline.value }).frames ?? []) as typeof timeline.value
    if (timeline.value.length) await showFrame(timeline.value[0].frame_id)
  } catch (e) {
    setErr(e)
  }
}

async function showFrame(frameId: number): Promise<void> {
  if (!lastVideoTaskId.value || !mediaPath.value) return
  currentFrameId.value = frameId
  loadingFrame.value = true
  try {
    const preview = await wsClient.request('result.preview', {
      video_path: mediaPath.value,
      frame_id: frameId
    })
    const dataUrl = (preview.data as { data_url?: string }).data_url || ''
    if (dataUrl) imageUrl.value = dataUrl
    const frameResp = await wsClient.request('result.frame', {
      task_id: lastVideoTaskId.value,
      frame_id: frameId
    })
    objects.value = ((frameResp.data as { objects?: BoxObject[] }).objects ?? []) as BoxObject[]
    selectedId.value = objects.value.length ? objects.value[0].id : null
  } catch (e) {
    setErr(e)
  } finally {
    loadingFrame.value = false
  }
}

function onTimelineInput(ev: Event): void {
  const v = Number((ev.target as HTMLInputElement).value)
  const item = timeline.value[v]
  if (item) void showFrame(item.frame_id)
}

async function startVideoInfer(): Promise<void> {
  if (!mediaPath.value) {
    errorMsg.value = '请先选择视频'
    return
  }
  if (!selectedModels.value.length) {
    errorMsg.value = t('workbench.noModel')
    return
  }
  running.value = true
  errorMsg.value = ''
  progressText.value = ''
  try {
    const resp = await wsClient.request('video.start', {
      media_path: mediaPath.value,
      model_ids: selectedModels.value,
      skip_frame: skipFrame.value,
      box_persistence: boxPersistence.value,
      profile_id: activeProfileId.value
    })
    const task = (resp.data as { task?: { task_id?: string } }).task
    lastVideoTaskId.value = task?.task_id || ''
    progressText.value = `${t('tasks.title')}: ${task?.task_id || ''}`
    if (lastVideoTaskId.value) void loadTimeline(lastVideoTaskId.value)
  } catch (e) {
    setErr(e)
  } finally {
    running.value = false
  }
}

async function startInfer(): Promise<void> {
  if (mode.value === 'video') {
    await startVideoInfer()
    return
  }
  if (mode.value === 'camera') {
    await startCamera()
    return
  }
  if (!mediaPath.value && !folderPath.value) {
    errorMsg.value = t('workbench.canvasHint')
    return
  }
  if (!selectedModels.value.length) {
    errorMsg.value = t('workbench.noModel')
    return
  }
  running.value = true
  errorMsg.value = ''
  progressText.value = ''
  try {
    if (folderPath.value && mediaPath.value === folderPath.value) {
      const resp = await wsClient.request('detect.folder', {
        folder_path: folderPath.value,
        model_ids: selectedModels.value,
        overrides: {
          conf: conf.value,
          skip_frame: skipFrame.value,
          box_persistence: boxPersistence.value
        },
        profile_id: activeProfileId.value
      })
      const task = (resp.data as { task?: { task_id?: string } }).task
      progressText.value = `${t('tasks.title')}: ${task?.task_id || ''}`
    } else {
      const resp = await wsClient.request('detect.image', {
        media_path: mediaPath.value,
        model_ids: selectedModels.value,
        overrides: {
          conf: conf.value,
          skip_frame: skipFrame.value,
          box_persistence: boxPersistence.value
        },
        profile_id: activeProfileId.value
      })
      const data = resp.data as {
        task?: { task_id?: string }
        frame?: { objects?: BoxObject[]; meta?: Record<string, unknown> }
      }
      lastImageTaskId.value = data.task?.task_id || ''
      objects.value = data.frame?.objects ?? []
      lastMeta.value = data.frame?.meta ?? null
      if (objects.value.length) selectedId.value = objects.value[0].id
    }
  } catch (e) {
    setErr(e)
  } finally {
    running.value = false
  }
}

async function startCamera(): Promise<void> {
  if (!selectedModels.value.length) {
    errorMsg.value = t('workbench.noModel')
    return
  }
  errorMsg.value = ''
  try {
    const payload: Record<string, unknown> = {
      source_type: camSourceType.value,
      model_ids: selectedModels.value,
      skip_frame: skipFrame.value,
      box_persistence: boxPersistence.value
    }
    if (camSourceType.value === 'usb') payload.device_index = camDeviceIndex.value
    else payload.source = camRtspUrl.value
    const resp = await wsClient.request('camera.open', payload)
    camStreamId.value = ((resp.data as { stream_id?: string }).stream_id) || ''
    camLive.value = true
    camFrameCount.value = 0
    camDetectCount.value = 0
  } catch (e) {
    setErr(e)
  }
}

async function stopCamera(): Promise<void> {
  if (!camStreamId.value) return
  try {
    await wsClient.request('camera.close', { stream_id: camStreamId.value })
  } catch (e) {
    setErr(e)
  } finally {
    camLive.value = false
    camStreamId.value = ''
  }
}

async function exportVideo(): Promise<void> {
  const api = window.yoloStudio
  if (!mediaPath.value) {
    errorMsg.value = '请先选择并检测视频'
    return
  }
  if (!lastVideoTaskId.value) {
    errorMsg.value = '请先执行视频检测'
    return
  }
  errorMsg.value = ''
  let outPath = ''
  if (api?.saveVideo) {
    const name = mediaPath.value.split(/[\\/]/).pop() || 'export.mp4'
    outPath = (await api.saveVideo(name.replace(/\.[^.]+$/, '') + '_检测.mp4')) || ''
    if (!outPath) return
  } else {
    errorMsg.value = '请在桌面端中导出'
    return
  }
  try {
    const resp = await wsClient.request('export.video', {
      source_video: mediaPath.value,
      output_path: outPath,
      source_task_id: lastVideoTaskId.value,
      label_template: labelTemplate.value
    })
    const task = (resp.data as { task?: { task_id?: string } }).task
    progressText.value = `${t('export.running')}: ${task?.task_id || ''}`
  } catch (e) {
    setErr(e)
  }
}

function toggleVisible(id: number): void {
  const o = objects.value.find((x) => x.id === id)
  if (!o) return
  const next = o.visible === false
  o.visible = next
  const taskId = mode.value === 'video' ? lastVideoTaskId.value : lastImageTaskId.value
  const frameId = mode.value === 'video' ? currentFrameId.value : 0
  if (!taskId) return
  void wsClient
    .request('ops.setVisible', {
      task_id: taskId,
      frame_id: frameId,
      object_id: id,
      model_id: o.model_id,
      visible: next
    })
    .catch((e) => setErr(e))
}

onMounted(() => {
  const tryLoad = () => {
    void loadModels()
    void loadProfiles()
  }
  tryLoad()
  wsClient.on('client.open', () => {
    errorMsg.value = ''
    tryLoad()
  })
  wsClient.on('task.progress', (msg: { data?: Record<string, unknown> }) => {
    const d = msg.data || {}
    const detail = d.progress_detail as { done?: number; total?: number; current_item?: string } | undefined
    if (detail && detail.total) {
      progressText.value = `${detail.done || 0}/${detail.total} ${detail.current_item || ''}`
    }
  })
  wsClient.on('task.done', (msg: { data?: Record<string, unknown> }) => {
    const d = msg.data || {}
    if (d.status === 'completed') {
      progressText.value = t('status.completed')
      lastVideoSummary.value = (d.summary as Record<string, unknown>) || null
      if (d.type === 'video' && lastVideoTaskId.value) void loadTimeline(lastVideoTaskId.value)
    }
    if (d.status === 'failed') progressText.value = `${t('status.failed')}: ${d.error || ''}`
  })
  wsClient.on('stream.frame', (msg: { data?: Record<string, unknown> }) => {
    const d = msg.data || {}
    if (camStreamId.value && d.stream_id !== camStreamId.value) return
    imageUrl.value = String(d.data_url || '')
    objects.value = (d.objects as BoxObject[]) || []
    camFrameCount.value = Number(d.frame_id || 0)
    camDetectCount.value = Number(d.detect_count || 0)
  })
  wsClient.on('stream.error', (msg: { data?: Record<string, unknown> }) => {
    errorMsg.value = formatError((msg.data as { message?: string })?.message || '摄像头错误')
    camLive.value = false
  })
  wsClient.on('stream.stopped', () => {
    camLive.value = false
  })
})

onUnmounted(() => {
  /* 这些监听器跟随应用进程生命周期存在。 */
})
</script>

<template>
  <!-- 通用工作台：承载图片、视频和摄像头检测及结果复核流程。 -->
  <div class="page workbench-page">
    <div class="page-header">
      <h1 class="page-title">{{ t('workbench.title') }}</h1>
      <div class="page-toolbar">
        <button type="button" :class="{ primary: mode === 'image' }" @click="mode = 'image'">
          {{ t('workbench.imageDetect') }}
        </button>
        <button type="button" :class="{ primary: mode === 'video' }" @click="mode = 'video'">
          {{ t('workbench.videoDetect') }}
        </button>
        <button type="button" :class="{ primary: mode === 'camera' }" @click="mode = 'camera'">
          {{ t('workbench.cameraLive') }}
        </button>
      </div>
    </div>

    <div class="toolbar-row">
      <button type="button" class="primary" @click="pickImage">{{ t('action.selectImage') }}</button>
      <button type="button" @click="pickFolder">{{ t('action.selectFolder') }}</button>
      <button type="button" @click="pickVideo">{{ t('action.selectVideo') }}</button>
      <span class="path-text num">{{ mediaPath || '—' }}</span>
      <button
        type="button"
        class="primary"
        :disabled="running || (!mediaPath && !folderPath) || !selectedModels.length"
        @click="startInfer"
      >
        {{ running ? t('status.running') : t('action.startInfer') }}
      </button>
      <button
        v-if="mode === 'video'"
        type="button"
        :disabled="!lastVideoTaskId || running"
        @click="exportVideo"
      >
        {{ t('action.exportVideo') }}
      </button>
      <template v-if="mode === 'camera'">
        <select v-model="camSourceType" class="sel">
          <option value="usb">{{ t('camera.usb') }}</option>
          <option value="rtsp">{{ t('camera.rtsp') }}</option>
        </select>
        <input
          v-if="camSourceType === 'usb'"
          v-model.number="camDeviceIndex"
          type="number"
          class="num-input narrow"
          min="0"
          :title="t('camera.deviceIndex')"
        />
        <input
          v-else
          v-model="camRtspUrl"
          class="text-input grow-url"
          :placeholder="t('camera.rtspPlaceholder')"
        />
        <button v-if="!camLive" type="button" class="primary" @click="startCamera">
          {{ t('camera.open') }}
        </button>
        <button v-else type="button" class="danger" @click="stopCamera">
          {{ t('camera.close') }}
        </button>
      </template>
    </div>

    <div class="sub-bar">
      <label class="lbl">{{ t('profile.label') }}</label>
      <select v-model="activeProfileId" class="sel" @change="applyProfile(activeProfileId)">
        <option v-for="p in profiles" :key="p.profile_id" :value="p.profile_id">
          {{ p.name }}
        </option>
      </select>
      <input v-model="profileName" class="text-input narrow" :placeholder="t('profile.namePlaceholder')" />
      <button type="button" class="ghost" @click="saveProfile">{{ t('profile.save') }}</button>
      <span v-if="camLive" class="muted-line num">
        {{ t('camera.frame') }} {{ camFrameCount }} · {{ t('camera.detect') }} {{ camDetectCount }}
      </span>
    </div>

    <p v-if="errorMsg" class="err-text">{{ errorMsg }}</p>
    <p v-if="progressText" class="muted-line">{{ progressText }}</p>

    <div v-if="timeline.length" class="timeline">
      <label class="lbl">{{ t('replay.timeline') }}</label>
      <input
        class="timeline-slider"
        type="range"
        :min="0"
        :max="timeline.length - 1"
        :value="timeline.findIndex((x) => x.frame_id === currentFrameId)"
        @input="onTimelineInput"
      />
      <span class="num timeline-text">
        {{ t('replay.frame') }} {{ currentFrameId }} · {{ timeline.length }} {{ t('replay.total') }}
      </span>
    </div>

    <div class="work-grid">
      <div class="canvas-panel">
        <CanvasStage
          v-if="imageUrl"
          :image-url="imageUrl"
          :objects="objects"
          :selected-id="selectedId"
          :label-template="labelTemplate"
          @select="(id) => (selectedId = id)"
        />
        <video
          v-else-if="videoUrl && mode === 'video'"
          class="video-preview"
          :src="videoUrl"
          controls
          muted
        />
        <EmptyState
          v-else
          icon="▣"
          :title="t('workbench.title')"
          :description="t('workbench.canvasHint')"
          :action-label="t('action.selectImage')"
          @action="pickImage"
        />
      </div>

      <div class="side-panel">
        <section class="panel compact">
          <div class="panel-head">
            <h2 class="panel-title">{{ t('workbench.modelSelect') }}</h2>
            <span class="badge">{{ selectedModels.length }}</span>
          </div>
          <div class="panel-body model-list">
            <label v-for="m in models" :key="m.model_id" class="model-item">
              <input v-model="selectedModels" type="checkbox" :value="m.model_id" />
              <span class="model-name">{{ m.name }}</span>
              <span class="badge" :class="m.loaded ? 'ok' : ''">
                {{ m.loaded ? t('models.loaded') : t('models.unloaded') }}
              </span>
            </label>
            <div v-if="!models.length" class="muted">{{ t('models.empty') }}</div>
          </div>
        </section>

        <section class="panel compact">
          <div class="panel-head">
            <h2 class="panel-title">{{ t('workbench.params') }}</h2>
          </div>
          <div class="panel-body param-grid">
            <span class="field-label">{{ t('workbench.confidence') }}</span>
            <input v-model.number="conf" type="number" min="0" max="1" step="0.05" class="num-input" />
            <span class="field-label">{{ t('workbench.labelTemplate') }}</span>
            <input v-model="labelTemplate" type="text" class="text-input" />
            <span class="field-label">{{ t('workbench.skipFrame') }}</span>
            <input v-model.number="skipFrame" type="number" min="1" step="1" class="num-input" />
            <span class="field-label">{{ t('workbench.boxPersistence') }}</span>
            <input v-model.number="boxPersistence" type="number" min="1" step="1" class="num-input" />
          </div>
        </section>

        <section class="panel compact grow-list">
          <div class="panel-head">
            <h2 class="panel-title">{{ t('workbench.results') }}（{{ objects.length }}）</h2>
          </div>
          <div class="panel-body result-list">
            <div
              v-for="o in resultItems"
              :key="o.id + '-' + o.model_id"
              class="result-item"
              :class="{ selected: selectedId === o.id }"
              @click="selectedId = o.id"
            >
              <span class="swatch" :style="{ background: o.style?.color || DEFAULT_BOX_COLOR }" />
              <span class="r-name">{{ o.id }}:{{ o.display }}</span>
              <span class="num r-conf">{{ o.confText }}</span>
              <button type="button" class="ghost mini" @click.stop="toggleVisible(o.id)">
                {{ o.visible === false ? '显示' : '隐藏' }}
              </button>
            </div>
            <div v-if="!resultItems.length" class="muted">{{ t('empty.noResult') }}</div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workbench-page {
  height: 100%;
  min-height: 0;
}
.toolbar-row,
.sub-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.lbl {
  color: var(--text-secondary);
  font-size: var(--text-sm);
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
.path-text {
  flex: 1;
  min-width: 60px;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
.timeline {
  display: flex;
  align-items: center;
  gap: 10px;
}
.timeline-slider {
  flex: 1;
  accent-color: var(--accent);
}
.timeline-text {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  white-space: nowrap;
}
.work-grid {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 12px;
  flex: 1;
  min-height: 360px;
}
.canvas-panel {
  min-height: 360px;
  display: flex;
}
.canvas-panel :deep(.canvas-wrap) {
  flex: 1;
}
.canvas-panel :deep(.empty-state) {
  flex: 1;
  min-height: 360px;
}
.video-preview {
  width: 100%;
  height: 100%;
  min-height: 360px;
  object-fit: contain;
  background: var(--bg-canvas);
  border-radius: var(--radius-lg);
}
.side-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}
.panel.compact .panel-head {
  padding: 8px 12px;
}
.panel.compact .panel-body {
  padding: 10px 12px;
}
.model-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.model-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--text-sm);
}
.model-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.param-grid {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px 10px;
  align-items: center;
}
.param-grid .field-label {
  text-align: right;
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
  width: 100%;
}
.text-input.narrow {
  width: 110px;
}
.num-input.narrow {
  width: 64px;
}
.grow-url {
  width: 160px;
}
.grow-list {
  flex: 1;
  min-height: 120px;
  display: flex;
  flex-direction: column;
}
.grow-list .panel-body {
  flex: 1;
  overflow: auto;
}
.result-item {
  display: grid;
  grid-template-columns: 12px 1fr 44px 44px;
  gap: 6px;
  align-items: center;
  padding: 5px 2px;
  border-bottom: 1px solid color-mix(in srgb, var(--border) 50%, transparent);
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
.r-conf {
  text-align: right;
  color: var(--text-secondary);
}
.mini {
  padding: 2px 6px;
  font-size: 11px;
}
.muted {
  color: var(--text-muted);
  font-size: var(--text-sm);
}
</style>
