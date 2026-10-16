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
import { DEFAULT_PACKAGE_SOURCE, type PackageSourceSelection } from '../shared/package-source'

const route = useRoute()
const router = useRouter()

interface RuntimeSetupView {
  managed: boolean
  phase: 'initializing' | 'ready' | 'failed'
  step: string
  message: string
  error: string
  details: string[]
  packageSource: PackageSourceSelection
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
  details: [],
  packageSource: { ...DEFAULT_PACKAGE_SOURCE }
})
const setupRetrying = ref(false)
let activeWsUrl = ''
let wsUrlRequestId = 0
let wsListenersRegistered = false
let stopRuntimeSetupStatus: (() => void) | undefined
const onProjectChanged = () => void refreshProjectLabel()

/** 复制主进程的初始化状态，供首次启动提示和错误重试界面使用。 */
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
// 独立摄像头窗口只渲染预览路由，避免带出导航、控制台和初始化遮罩。
const isCameraPopout = computed(() => route.name === 'camera-popout' || route.path === '/camera-popout')

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

/** 注册一次 WebSocket 生命周期监听，并连接指定的本地后端地址。 */
function connectWs(url: string): void {
  if (activeWsUrl === url) return
  activeWsUrl = url
  wsState.value = 'connecting'
  if (!wsListenersRegistered) {
    wsClient.on('client.open', () => {
      wsState.value = 'connected'
      pushLog('INFO', 'ws', '通信已连接')
      void checkHealth()
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
      /* 心跳响应只用于维持连接，不重复写入日志。 */
    })
    wsClient.on('project.open', () => void refreshProjectLabel())
    wsClient.on('project.create', () => void refreshProjectLabel())
    wsListenersRegistered = true
  }
  wsClient.connect(url)
}

/** 仅在后端就绪后获取地址；请求序号用于丢弃过期的地址响应。 */
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
    /* 后端状态由主进程 supervisor 事件统一提供。 */
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

/** 响应初始化失败提示中的重试操作，并把新状态反馈到界面。 */
async function retryRuntimeSetup(packageSource: PackageSourceSelection): Promise<void> {
  const api = window.yoloStudio
  if (!api?.retryRuntimeSetup || setupRetrying.value) return
  setupRetrying.value = true
  try {
    applyRuntimeSetupStatus(await api.retryRuntimeSetup(packageSource))
  } catch (error) {
    pushLog('ERROR', 'runtime', error instanceof Error ? error.message : String(error))
  } finally {
    setupRetrying.value = false
  }
}

/** 恢复主题、订阅主进程事件并建立后端 WebSocket 连接。 */
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
    /* 项目当前状态不可用时保持已有标签。 */
  }
}

onMounted(() => {
  void bootstrap()
  window.addEventListener('yolo-project-changed', onProjectChanged)
})
onUnmounted(() => {
  window.removeEventListener('yolo-project-changed', onProjectChanged)
  stopRuntimeSetupStatus?.()
  wsClient.close()
})
watch(() => route.path, () => {
  /* 预留给未来按路由更新辅助面板上下文。 */
})
</script>

<template>
  <router-view v-if="isCameraPopout" />
  <!-- 应用外壳：汇总导航、后端状态、控制台和首次运行提示。 -->
  <div v-else class="shell">
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
      :retrying="setupRetrying"
      @retry-runtime="retryRuntimeSetup"
    />
  </div>
</template>
