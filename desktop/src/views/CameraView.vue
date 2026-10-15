<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import CanvasStage, { type BoxObject } from '../components/CanvasStage.vue'
import ModelPicker from '../components/ModelPicker.vue'
import LabelConfigModal from '../components/LabelConfigModal.vue'
import { defaultLabelSettings, type LabelSettings } from '../components/labelTypes'
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

const embed = window.location.hash.includes('embed=1')

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
const zoom = ref(1)
const showLabelCfg = ref(false)
const labelSettings = ref<LabelSettings>(defaultLabelSettings())
const stageRef = ref<HTMLElement | null>(null)

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

async function syncModelsToStream(): Promise<void> {
  if (!camStreamId.value) return
  try {
    await wsClient.request('camera.setModels', {
      stream_id: camStreamId.value,
      model_ids: selectedModels.value
    })
    infoMsg.value = selectedModels.value.length
      ? `已切换模型：${selectedModels.value.join('、')}`
      : '已关闭检测，仅预览'
  } catch (e) {
    setErr(e)
  }
}

async function startCamera(): Promise<void> {
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
  if (!camStreamId.value || !api?.saveVideo) return
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
    const data = resp.data as { output_path?: string; task_id?: string; record_frames?: number }
    recordPath.value = data.output_path || recordPath.value
    recordTaskId.value = data.task_id || recordTaskId.value
    infoMsg.value = `已保存 ${data.record_frames ?? 0} 帧`
  } catch (e) {
    setErr(e)
  }
}

function openInEditor(): void {
  if (!recordPath.value) return
  sessionStorage.setItem('editor_video_path', recordPath.value)
  sessionStorage.setItem('editor_task_id', recordTaskId.value || '')
  void import('../router').then(({ router }) => router.push('/video-editor'))
}

function setZoom(z: number): void {
  zoom.value = Math.min(4, Math.max(0.5, z))
}

function toggleFullscreen(): void {
  const el = stageRef.value
  if (!el) return
  if (document.fullscreenElement) void document.exitFullscreen()
  else void el.requestFullscreen()
}

function openPopout(): void {
  void window.yoloStudio?.openCameraWindow?.()
}

const liveLabel = computed(() => (camLive.value ? t('backend.ready') : t('camera.empty')))

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
  })
})
onUnmounted(() => {
  void stopCamera()
})
</script>

<template>
  <div class="cam-shell" :class="{ embed }">
    <!-- left: source + models -->
    <aside v-if="!embed" class="cam-side left">
      <section class="panel">
        <div class="panel-head"><h3>{{ t('camera.usb') }} / {{ t('camera.rtsp') }}</h3></div>
        <div class="panel-body col">
          <select v-model="camSourceType" class="ctl">
            <option value="usb">{{ t('camera.usb') }}</option>
            <option value="rtsp">{{ t('camera.rtsp') }}</option>
          </select>
          <input
            v-if="camSourceType === 'usb'"
            v-model.number="camDeviceIndex"
            type="number"
            min="0"
            class="ctl"
          />
          <input v-else v-model="camRtspUrl" class="ctl" :placeholder="t('camera.rtspPlaceholder')" />
          <button type="button" class="primary" :disabled="camLive" @click="startCamera">
            {{ t('camera.open') }}
          </button>
          <button type="button" class="danger" :disabled="!camLive" @click="stopCamera">
            {{ t('camera.close') }}
          </button>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3>{{ t('workbench.modelSelect') }}</h3>
          <span class="hint">可不选；运行中可热切换</span>
        </div>
        <div class="panel-body">
          <ModelPicker
            v-model:selected="selectedModels"
            :models="models"
            compact
            @update:selected="() => { if (camLive) void syncModelsToStream() }"
          />
          <button type="button" class="ghost mini" :disabled="!camLive" @click="syncModelsToStream">
            应用到摄像头
          </button>
        </div>
      </section>
    </aside>

    <!-- center: monitor -->
    <main ref="stageRef" class="cam-stage">
      <div class="stage-toolbar">
        <button type="button" class="ghost mini" @click="setZoom(zoom - 0.2)">−</button>
        <span class="num">{{ Math.round(zoom * 100) }}%</span>
        <button type="button" class="ghost mini" @click="setZoom(zoom + 0.2)">+</button>
        <button type="button" class="ghost mini" @click="setZoom(1)">复位</button>
        <span class="spacer" />
        <button type="button" class="ghost mini" @click="toggleFullscreen">
          {{ t('camera.fullscreen') }}
        </button>
        <button v-if="!embed" type="button" class="ghost mini" @click="showLabelCfg = true">标签配置</button>
        <button v-if="!embed" type="button" class="ghost mini" @click="openPopout">
          {{ t('camera.popout') }}
        </button>
        <span class="status-pill" :class="{ on: camLive }">{{ liveLabel }}</span>
      </div>
      <div class="stage-frame" :style="{ transform: `scale(${zoom})` }">
        <CanvasStage
          v-if="imageUrl"
          :image-url="imageUrl"
          :objects="objects"
          :selected-id="selectedId"
          :label-settings="labelSettings"
          @select="(id) => (selectedId = id)"
        />
        <EmptyState v-else icon="⬡" :title="t('workbench.cameraLive')" :description="t('camera.empty')" />
      </div>
    </main>

    <!-- right: params + record -->
    <aside v-if="!embed" class="cam-side right">
      <section class="panel">
        <div class="panel-head"><h3>{{ t('workbench.params') }}</h3></div>
        <div class="panel-body col">
          <label>{{ t('workbench.skipFrame') }}</label>
          <input v-model.number="skipFrame" type="number" min="1" class="ctl" />
          <label>{{ t('workbench.boxPersistence') }}</label>
          <input v-model.number="boxPersistence" type="number" min="1" class="ctl" />
          <label>{{ t('camera.recordFps') }}</label>
          <input v-model.number="recordFps" type="number" min="1" :max="maxFps" class="ctl" />
          <span class="hint">≤ {{ maxFps }} fps</span>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head"><h3>{{ t('camera.recordStart') }}</h3></div>
        <div class="panel-body col">
          <button v-if="!recording" type="button" class="primary" :disabled="!camLive" @click="startRecord">
            ● {{ t('camera.recordStart') }}
          </button>
          <button v-else type="button" class="danger" @click="stopRecord">
            ■ {{ t('camera.recordStop') }}
          </button>
          <button v-if="recordPath && !recording" type="button" @click="openInEditor">
            {{ t('camera.openEditor') }}
          </button>
          <div class="hint num">
            {{ t('camera.frame') }} {{ camFrameCount }} · {{ t('camera.detect') }} {{ camDetectCount }}
          </div>
        </div>
      </section>
    </aside>

    <LabelConfigModal
      v-model:visible="showLabelCfg"
      v-model:model-value="labelSettings"
      @apply="(s) => { labelSettings = s }"
    />
    <p v-if="errorMsg && !embed" class="err">{{ errorMsg }}</p>
    <p v-if="infoMsg && !embed" class="info">{{ infoMsg }}</p>
  </div>
</template>

<style scoped>
.cam-shell {
  display: grid;
  grid-template-columns: 240px 1fr 240px;
  grid-template-rows: 1fr auto;
  gap: 10px;
  padding: 10px;
  height: 100%;
  min-height: 0;
}
.cam-shell.embed {
  grid-template-columns: 1fr;
  padding: 0;
}
.cam-side {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow: auto;
  grid-row: 1 / 3;
}
.cam-side.right {
  grid-column: 3;
}
.cam-stage {
  grid-column: 2;
  grid-row: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: var(--bg-canvas);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.cam-shell.embed .cam-stage {
  grid-column: 1;
  border: none;
  border-radius: 0;
}
.stage-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--bg-chrome);
  border-bottom: 1px solid var(--border);
}
.spacer {
  flex: 1;
}
.status-pill {
  font-size: var(--text-xs);
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-inset);
  color: var(--text-muted);
}
.status-pill.on {
  background: var(--success-soft);
  color: var(--success);
}
.stage-frame {
  flex: 1;
  min-height: 0;
  transform-origin: center center;
  transition: transform 150ms var(--ease);
}
.panel {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}
.panel-head {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 8px;
}
.panel-head h3 {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: 600;
}
.panel-body {
  padding: 10px 12px;
}
.col {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ctl {
  height: 30px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0 8px;
  background: var(--bg-inset);
  color: var(--text-primary);
}
.hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
}
.mini {
  padding: 3px 8px;
  font-size: 11px;
}
.err {
  grid-column: 1 / -1;
  color: var(--danger);
  margin: 0;
  font-size: var(--text-sm);
}
.info {
  grid-column: 1 / -1;
  color: var(--success);
  margin: 0;
  font-size: var(--text-sm);
}
@media (max-width: 1100px) {
  .cam-shell {
    grid-template-columns: 200px 1fr;
  }
  .cam-side.right {
    display: none;
  }
}
</style>
