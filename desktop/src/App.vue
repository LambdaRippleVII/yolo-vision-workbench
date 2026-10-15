<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import SideNav from './components/SideNav.vue'
import TopModeBar from './components/TopModeBar.vue'
import BootSplash from './components/BootSplash.vue'
import ConsoleDock from './components/ConsoleDock.vue'
import StartupSetupOverlay from './components/StartupSetupOverlay.vue'
import type { LogLine } from './components/ConsoleDock.vue'
import { wsClient } from './api/ws'
import type { Envelope } from './api/protocol'
import { t } from './locales'

const route = useRoute()
const router = useRouter()

interface RuntimeSetupView {
  managed: boolean
  phase: 'initializing' | 'ready' | 'failed'
  step: string
  message: string
  error: string
  details: string[]
}

interface StartupModel {
  model_id: string
  name: string
  downloadable?: boolean
  weights_available?: boolean
}

interface StartupModelView {
  visible: boolean
  phase: 'idle' | 'checking' | 'downloading' | 'failed' | 'complete'
  message: string
  currentModelId: string
  models: Array<{
    model_id: string
    name: string
    state: 'waiting' | 'downloading' | 'failed' | 'ready'
    error?: string
  }>
}

const theme = ref<'light' | 'dark'>('light')
const backend = ref<{
  status: string
  restarts: number
  port: number
  host: string
  message: string
  reusedPid?: number
}>({ status: 'unknown', restarts: 0, port: 8765, host: '127.0.0.1', message: '' })
const wsState = ref<'connecting' | 'connected' | 'disconnected'>('connecting')
const pingMs = ref<number | null>(null)
const logs = ref<LogLine[]>([])
const consoleExpanded = ref(false)
const projectLabel = ref('')
const runtimeSetup = ref<RuntimeSetupView>({
  managed: false,
  phase: 'ready',
  step: '开发环境',
  message: '开发环境由当前 Python 配置提供。',
  error: '',
  details: []
})
const startupModels = ref<StartupModelView>({
  visible: false,
  phase: 'idle',
  message: '',
  currentModelId: '',
  models: []
})
const setupRetrying = ref(false)
let activeWsUrl = ''
let wsUrlRequestId = 0
let wsListenersRegistered = false
let startupModelCheckStarted = false
let stopRuntimeSetupStatus: (() => void) | undefined
let stopStartupModelProgress: (() => void) | undefined
const onProjectChanged = () => void refreshProjectLabel()

function applyRuntimeSetupStatus(status: RuntimeSetupView): void {
  runtimeSetup.value = { ...status, details: [...status.details] }
}

function applyBackendStatus(s: {
  status: string
  restarts: number
  port: number
  host: string
  message?: string
  reusedPid?: number
}): void {
  backend.value = {
    status: s.status,
    restarts: s.restarts,
    port: s.port,
    host: s.host,
    message: s.message || '',
    reusedPid: s.reusedPid
  }
}

const showAside = computed(() => route.path.startsWith('/workbench') || route.path.startsWith('/models'))

function applyTheme(next: 'light' | 'dark'): void {
  theme.value = next
  document.documentElement.setAttribute('data-theme', next)
  localStorage.setItem('yolo-vision-workbench-theme', next)
}

function toggleTheme(): void {
  applyTheme(theme.value === 'dark' ? 'light' : 'dark')
}

function pushLog(level: string, source: string, message: string): void {
  logs.value.unshift({
    ts: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
    level,
    source,
    message
  })
  if (logs.value.length > 300) logs.value.pop()
}

async function checkBuiltinModelsOnStartup(): Promise<void> {
  if (!runtimeSetup.value.managed || startupModelCheckStarted || wsState.value !== 'connected') return
  startupModelCheckStarted = true
  startupModels.value = {
    visible: true,
    phase: 'checking',
    message: '正在检查内置模型权重…',
    currentModelId: '',
    models: []
  }

  try {
    const response = await wsClient.request('model.list', {}, 30_000)
    const items = ((response.data as { models?: StartupModel[] }).models ?? []) as StartupModel[]
    const missing = items.filter((model) => model.downloadable && model.weights_available === false)
    if (!missing.length) {
      startupModels.value = {
        visible: false,
        phase: 'idle',
        message: '',
        currentModelId: '',
        models: []
      }
      return
    }

    startupModels.value = {
      visible: true,
      phase: 'downloading',
      message: `发现 ${missing.length} 个内置模型缺少权重，正在自动下载…`,
      currentModelId: missing[0]?.model_id || '',
      models: missing.map((model) => ({
        model_id: model.model_id,
        name: model.name,
        state: 'waiting'
      }))
    }
    await downloadStartupModels(missing.map((model) => model.model_id))
  } catch (error) {
    startupModels.value = {
      visible: true,
      phase: 'failed',
      message: `检查内置模型失败：${error instanceof Error ? error.message : String(error)}`,
      currentModelId: '',
      models: []
    }
    startupModelCheckStarted = false
  }
}

async function downloadStartupModels(modelIds: string[]): Promise<void> {
  if (!modelIds.length || setupRetrying.value) return
  setupRetrying.value = true
  startupModels.value = {
    ...startupModels.value,
    visible: true,
    phase: 'downloading',
    message: '正在下载缺少的内置模型权重…',
    currentModelId: modelIds[0] || '',
    models: startupModels.value.models.map((model) =>
      modelIds.includes(model.model_id)
        ? { ...model, state: 'waiting', error: undefined }
        : model
    )
  }

  try {
    const response = await wsClient.request(
      'model.downloadBuiltin',
      { model_ids: modelIds },
      30 * 60 * 1000
    )
    const results = (response.data as {
      results?: Array<{ model_id: string; ok: boolean; error?: string }>
    }).results ?? []
    const byId = new Map(results.map((result) => [result.model_id, result]))
    startupModels.value.models = startupModels.value.models.map((model) => {
      if (!modelIds.includes(model.model_id)) return model
      const result = byId.get(model.model_id)
      return result?.ok
        ? { ...model, state: 'ready', error: undefined }
        : {
            ...model,
            state: 'failed',
            error: result?.error || '后端没有返回下载结果。'
          }
    })
    const failures = startupModels.value.models.filter((model) => model.state === 'failed')
    if (failures.length) {
      startupModels.value.phase = 'failed'
      startupModels.value.message = `${failures.length} 个模型下载失败，可单独重试或稍后在「模型管理」中补齐。`
    } else {
      startupModels.value.phase = 'complete'
      startupModels.value.message = '所有缺失的内置模型权重已下载完成。'
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    startupModels.value.models = startupModels.value.models.map((model) =>
      modelIds.includes(model.model_id) ? { ...model, state: 'failed', error: message } : model
    )
    startupModels.value.phase = 'failed'
    startupModels.value.message = `模型下载中断：${message}`
  } finally {
    setupRetrying.value = false
    window.dispatchEvent(new Event('yolo-models-changed'))
  }
}

function retryStartupModels(): void {
  const failedIds = startupModels.value.models
    .filter((model) => model.state === 'failed')
    .map((model) => model.model_id)
  if (failedIds.length) {
    void downloadStartupModels(failedIds)
    return
  }
  startupModelCheckStarted = false
  void checkBuiltinModelsOnStartup()
}

function retryStartupModel(modelId: string): void {
  void downloadStartupModels([modelId])
}

function continueStartup(): void {
  startupModels.value.visible = false
}

function onStartupModelProgress(message: Envelope): void {
  if (startupModels.value.phase !== 'downloading') return
  const data = message.data as { model_id?: string; message?: string } | undefined
  if (!data?.model_id || !data.message) return
  startupModels.value.currentModelId = data.model_id
  startupModels.value.message = data.message
  startupModels.value.models = startupModels.value.models.map((model) =>
    model.model_id === data.model_id ? { ...model, state: 'downloading' } : model
  )
}

function connectWs(url: string): void {
  if (activeWsUrl === url) return
  activeWsUrl = url
  wsState.value = 'connecting'
  if (!wsListenersRegistered) {
    wsClient.on('client.open', () => {
      wsState.value = 'connected'
      pushLog('INFO', 'ws', '通信已连接')
      void checkHealth()
      void checkBuiltinModelsOnStartup()
    })
    wsClient.on('client.close', () => {
      wsState.value = 'disconnected'
      pingMs.value = null
    })
    wsClient.on('system.hello', (msg: Envelope) => {
      const ver = (msg.data as { server_version?: string }).server_version ?? ''
      pushLog('INFO', 'ws', `后端服务已握手（v${ver}）`)
      void checkHealth()
      void refreshProjectLabel()
    })
    wsClient.on('log.message', (msg: Envelope) => {
      const d = msg.data as { level?: string; message?: string; logger?: string }
      pushLog(d.level || 'INFO', d.logger || 'backend', d.message || '')
    })
    wsClient.on('pong', () => {
      /* keep-alive */
    })
    wsClient.on('project.open', () => void refreshProjectLabel())
    wsClient.on('project.create', () => void refreshProjectLabel())
    stopStartupModelProgress = wsClient.on('model.download.progress', onStartupModelProgress)
    wsListenersRegistered = true
  }
  wsClient.connect(url)
}

async function connectToBackend(): Promise<void> {
  const api = window.yoloStudio
  if (!api) return
  if (backend.value.status !== 'ready' && backend.value.status !== 'reused') {
    wsUrlRequestId += 1
    return
  }

  const requestId = ++wsUrlRequestId
  try {
    const wsUrl = await api.getWsUrl()
    if (requestId === wsUrlRequestId) connectWs(wsUrl)
  } catch (e) {
    if (requestId === wsUrlRequestId) pushLog('ERROR', 'ws', String(e))
  }
}

async function checkHealth(): Promise<void> {
  try {
    const res = await fetch(`http://${backend.value.host}:${backend.value.port}/health`, {
      signal: AbortSignal.timeout(2000)
    })
    if (res.ok) {
      const data = (await res.json()) as { status?: string }
      if (data.status === 'ready') {
        backend.value.status = backend.value.status === 'reused' ? 'reused' : 'ready'
      }
    }
  } catch {
    /* status comes from supervisor events */
  }
}

async function onPing(): Promise<void> {
  const t0 = Date.now()
  try {
    await wsClient.request('ping', {})
    pingMs.value = Date.now() - t0
  } catch (e) {
    pushLog('ERROR', 'ws', String(e))
  }
}

async function onRestart(): Promise<void> {
  const api = window.yoloStudio
  if (!api) return
  pushLog('WARN', 'supervisor', '正在重启后端服务…')
  try {
    const st = await api.restartBackend()
    applyBackendStatus(st)
    await connectToBackend()
    pushLog('INFO', 'supervisor', `后端服务状态：${st.status}`)
  } catch (error) {
    pushLog('ERROR', 'supervisor', error instanceof Error ? error.message : String(error))
  }
}

async function retryRuntimeSetup(): Promise<void> {
  const api = window.yoloStudio
  if (!api?.retryRuntimeSetup || setupRetrying.value) return
  setupRetrying.value = true
  try {
    applyRuntimeSetupStatus(await api.retryRuntimeSetup())
  } catch (error) {
    pushLog('ERROR', 'runtime', error instanceof Error ? error.message : String(error))
  } finally {
    setupRetrying.value = false
  }
}

async function bootstrap(): Promise<void> {
  const saved = localStorage.getItem('yolo-vision-workbench-theme')
  applyTheme(saved === 'dark' ? 'dark' : 'light')

  const api = window.yoloStudio
  if (api) {
    stopRuntimeSetupStatus = api.onRuntimeSetupStatus?.(applyRuntimeSetupStatus)
    const runtimeStatus = await api.getRuntimeSetupStatus?.()
    if (runtimeStatus) applyRuntimeSetupStatus(runtimeStatus)
    api.onBackendStatus((s) => {
      const endpointChanged = backend.value.host !== s.host || backend.value.port !== s.port
      applyBackendStatus(s)
      if (endpointChanged && activeWsUrl) {
        activeWsUrl = ''
        wsClient.close()
        wsState.value = 'connecting'
      }
      pushLog('INFO', 'supervisor', `后端服务状态：${s.status}${s.port ? ` :${s.port}` : ''}${s.message ? ` · ${s.message}` : ''}`)
      void connectToBackend()
    })
    api.onBackendLog((e) => pushLog(e.level, e.source, e.message))
    api.onMenuAction?.((payload) => {
      if (payload.action === 'openProject' || payload.action === 'newProject') {
        void router.push('/projects')
      } else if (payload.action === 'about') {
        pushLog('INFO', 'app', t('settings.aboutText'))
      } else if (payload.action === 'health') {
        void onPing()
      }
    })

    const st = await api.getBackendStatus()
    applyBackendStatus(st)
    await connectToBackend()
  } else {
    backend.value = {
      status: 'starting',
      restarts: 0,
      port: 8765,
      host: '127.0.0.1',
      message: '正在连接后端…'
    }
    connectWs('ws://127.0.0.1:8765/ws')
    void checkHealth()
    void onPing()
  }
}

async function refreshProjectLabel(): Promise<void> {
  try {
    const resp = await wsClient.request('project.current', {})
    const p = (resp.data as { project?: { name?: string } }).project
    projectLabel.value = p?.name || ''
  } catch {
    /* ignore */
  }
}

onMounted(() => {
  void bootstrap()
  window.addEventListener('yolo-project-changed', onProjectChanged)
})
onUnmounted(() => {
  window.removeEventListener('yolo-project-changed', onProjectChanged)
  stopRuntimeSetupStatus?.()
  stopStartupModelProgress?.()
  wsClient.close()
})
watch(() => route.path, () => {
  /* reserved for context-aware aside */
})
</script>

<template>
  <div class="shell">
    <BootSplash :status="backend.status" :message="backend.message" />

    <AppHeader
      :backend="backend"
      :ws-state="wsState"
      :ping-ms="pingMs"
      :theme="theme"
      :project-label="projectLabel"
      :backend-message="backend.message"
      @restart="onRestart"
      @toggle-theme="toggleTheme"
    >
      <template #modes>
        <TopModeBar />
      </template>
    </AppHeader>

    <div class="shell-body" :class="{ 'no-aside': !showAside }">
      <SideNav />
      <main class="shell-main">
        <router-view v-slot="{ Component, route }">
          <keep-alive>
            <component :is="Component" v-if="route.meta.keepAlive" :key="route.name" />
          </keep-alive>
          <component :is="Component" v-if="!route.meta.keepAlive" :key="route.name" />
        </router-view>
      </main>
      <aside v-if="showAside" class="shell-aside">
        <section class="aside-section">
          <h3 class="aside-section-title">{{ t('panel.properties') }}</h3>
          <div class="aside-section-body">
            <div class="field-row">
              <span class="field-label">{{ t('backend.label') }}</span>
              <span class="field-value">
                <span class="badge" :class="backend.status === 'ready' ? 'ok' : 'warn'">
                  {{ backend.status === 'ready' ? t('backend.ready') : t('backend.unknown') }}
                </span>
              </span>
            </div>
            <div class="field-row">
              <span class="field-label">{{ t('ws.label') }}</span>
              <span class="field-value">
                {{ wsState === 'connected' ? t('ws.connected') : t('ws.disconnected') }}
              </span>
            </div>
          </div>
        </section>

        <section class="aside-section">
          <h3 class="aside-section-title">{{ t('workbench.params') }}</h3>
          <div class="aside-section-body">
            <div class="field-row">
              <span class="field-label">{{ t('workbench.modelSelect') }}</span>
              <span class="field-value">{{ t('workbench.noModel') }}</span>
            </div>
            <div class="field-row">
              <span class="field-label">{{ t('workbench.confidence') }}</span>
              <span class="field-value num">0.45</span>
            </div>
          </div>
        </section>

        <section class="aside-section">
          <h3 class="aside-section-title">{{ t('ws.health') }}</h3>
          <div class="aside-section-body">
            <button type="button" class="primary" @click="onPing">{{ t('ws.ping') }}</button>
            <div class="field-row">
              <span class="field-label">延迟</span>
              <span class="field-value num">{{ pingMs !== null ? pingMs + ' ms' : '—' }}</span>
            </div>
          </div>
        </section>
      </aside>
    </div>

    <ConsoleDock
      v-model:expanded="consoleExpanded"
      :logs="logs"
      @clear="logs = []"
    />

    <StartupSetupOverlay
      :runtime="runtimeSetup"
      :models="startupModels"
      :retrying="setupRetrying"
      @retry-runtime="retryRuntimeSetup"
      @retry-models="retryStartupModels"
      @retry-model="retryStartupModel"
      @continue="continueStartup"
    />
  </div>
</template>
