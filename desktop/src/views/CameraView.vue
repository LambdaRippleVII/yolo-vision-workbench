<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import CanvasStage, { type BoxObject } from '../components/CanvasStage.vue'
import ModelPicker from '../components/ModelPicker.vue'
import EmptyState from '../components/EmptyState.vue'
import { wsClient } from '../api/ws'
import { formatError } from '../utils/errors'
import { t } from '../locales'

interface ModelItem {
  model_id: string
  name: string
  loaded: boolean
  class_list?: Array<{ class_id: number; class_name: string; display_name: string }>
}

const camSourceType = ref<'usb' | 'rtsp'>('usb')
const camDeviceIndex = ref(0)
const camRtspUrl = ref('')
const camStreamId = ref('')
const camLive = ref(false)
const recording = ref(false)
const recordFps = ref(15)
const maxFps = ref(30)
const recordPath = ref('')
const recordTaskId = ref('')
const imageUrl = ref('')
const objects = ref<BoxObject[]>([])
const selectedId = ref<number | null>(null)
const models = ref<ModelItem[]>([])
const selectedModels = ref<string[]>([])
const skipFrame = ref(5)
const boxPersistence = ref(5)
const errorMsg = ref('')
const infoMsg = ref('')
const camFrameCount = ref(0)
const camDetectCount = ref(0)

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
      box_persistence: Math.min(boxPersistence.value, skipFrame.value)
    }
    if (camSourceType.value === 'usb') payload.device_index = camDeviceIndex.value
    else payload.source = camRtspUrl.value
    const resp = await wsClient.request('camera.open', payload)
    camStreamId.value = String((resp.data as { stream_id?: string }).stream_id || '')
    camLive.value = true
  } catch (e) {
    setErr(e)
  }
}

async function stopCamera(): Promise<void> {
  if (recording.value) await stopRecord()
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

async function startRecord(): Promise<void> {
  const api = window.yoloStudio
  if (!camStreamId.value) return
  if (!api?.saveVideo) {
    errorMsg.value = '请在桌面端中录制'
    return
  }
  const out = (await api.saveVideo('录制_' + Date.now() + '.mp4')) || ''
  if (!out) return
  try {
    const resp = await wsClient.request('camera.record', {
      stream_id: camStreamId.value,
      action: 'start',
      output_path: out,
      fps: Math.min(recordFps.value, maxFps.value)
    })
    recordPath.value = out
    recordTaskId.value = String((resp.data as { task_id?: string }).task_id || '')
    recording.value = true
    infoMsg.value = `录制中 ${Math.min(recordFps.value, maxFps.value)}fps → ${out}`
  } catch (e) {
    setErr(e)
  }
}

async function stopRecord(): Promise<void> {
  if (!camStreamId.value) return
  try {
    const resp = await wsClient.request('camera.record', {
      stream_id: camStreamId.value,
      action: 'stop'
    })
    recording.value = false
    const data = resp.data as {
      output_path?: string
      record_frames?: number
      task_id?: string
    }
    recordPath.value = data.output_path || recordPath.value
    recordTaskId.value = data.task_id || recordTaskId.value
    infoMsg.value = `已保存录制 ${data.record_frames ?? 0} 帧 → ${data.output_path || recordPath.value}`
  } catch (e) {
    setErr(e)
  }
}

function openInEditor(): void {
  if (!recordPath.value) {
    errorMsg.value = '请先录制视频'
    return
  }
  // pass task_id so editor loads existing results without re-detect
  sessionStorage.setItem('editor_video_path', recordPath.value)
  sessionStorage.setItem('editor_task_id', recordTaskId.value || '')
  void import('../router').then(({ router }) => router.push('/video-editor'))
}

onMounted(() => {
  void loadModels()
  wsClient.on('client.open', () => void loadModels())
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
    recording.value = false
  })
})
onUnmounted(() => {
  void stopCamera()
})
</script>

<template>
  <div class="page camera-page">
    <div class="page-header">
      <h1 class="page-title">{{ t('workbench.cameraLive') }}</h1>
      <div class="page-toolbar">
        <select v-model="camSourceType" class="sel">
          <option value="usb">{{ t('camera.usb') }}</option>
          <option value="rtsp">{{ t('camera.rtsp') }}</option>
        </select>
        <input
          v-if="camSourceType === 'usb'"
          v-model.number="camDeviceIndex"
          type="number"
          class="num-input"
          min="0"
        />
        <input
          v-else
          v-model="camRtspUrl"
          class="text-input url"
          :placeholder="t('camera.rtspPlaceholder')"
        />
        <button v-if="!camLive" type="button" class="primary" @click="startCamera">
          {{ t('camera.open') }}
        </button>
        <button v-else type="button" class="danger" @click="stopCamera">
          {{ t('camera.close') }}
        </button>
        <button v-if="camLive && !recording" type="button" class="primary" @click="startRecord">
          ● {{ t('camera.recordStart') }}
        </button>
        <button v-if="recording" type="button" class="danger" @click="stopRecord">
          ■ {{ t('camera.recordStop') }}
        </button>
        <label class="lbl">{{ t('camera.recordFps') }}</label>
        <input v-model.number="recordFps" type="number" min="1" :max="maxFps" class="num-input" />
        <span class="muted">≤ {{ maxFps }} fps</span>
        <button v-if="recordPath && !recording" type="button" @click="openInEditor">
          {{ t('camera.openEditor') }}
        </button>
      </div>
    </div>

    <div class="sub">
      <ModelPicker v-model:selected="selectedModels" :models="models" compact />
      <label class="lbl">{{ t('workbench.skipFrame') }}</label>
      <input v-model.number="skipFrame" type="number" min="1" class="num-input" />
      <label class="lbl">{{ t('workbench.boxPersistence') }}</label>
      <input v-model.number="boxPersistence" type="number" min="1" class="num-input" />
      <span v-if="camLive" class="muted num">
        {{ t('camera.frame') }} {{ camFrameCount }} · {{ t('camera.detect') }} {{ camDetectCount }}
        <template v-if="recording"> · ●REC</template>
      </span>
    </div>

    <p v-if="errorMsg" class="err-text">{{ errorMsg }}</p>
    <p v-if="infoMsg" class="muted-line">{{ infoMsg }}</p>

    <div class="stage">
      <CanvasStage
        v-if="imageUrl"
        :image-url="imageUrl"
        :objects="objects"
        :selected-id="selectedId"
        @select="(id) => (selectedId = id)"
      />
      <EmptyState v-else icon="⬡" :title="t('workbench.cameraLive')" :description="t('camera.empty')" />
    </div>
  </div>
</template>

<style scoped>
.camera-page {
  height: 100%;
}
.sub {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.sel,
.num-input,
.text-input {
  height: 28px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-panel);
  color: var(--text-primary);
  padding: 0 8px;
  font-size: var(--text-sm);
}
.num-input {
  width: 64px;
}
.url {
  width: 200px;
}
.lbl {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--text-sm);
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
}
.err-text {
  color: var(--danger);
  margin: 0;
  font-size: var(--text-sm);
}
.muted-line,
.muted {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
.stage {
  flex: 1;
  min-height: 360px;
  display: flex;
}
.stage :deep(.canvas-wrap),
.stage :deep(.empty-state) {
  flex: 1;
}
</style>
