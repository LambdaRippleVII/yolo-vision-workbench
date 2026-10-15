<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import SideNav from './components/SideNav.vue'
import TopModeBar from './components/TopModeBar.vue'
import BootSplash from './components/BootSplash.vue'
import ConsoleDock from './components/ConsoleDock.vue'
import type { LogLine } from './components/ConsoleDock.vue'
import { wsClient } from './api/ws'
import type { Envelope } from './api/protocol'
import { t } from './locales'

const route = useRoute()
const router = useRouter()

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

function connectWs(url: string): void {
  wsState.value = 'connecting'
  wsClient.connect(url)

  wsClient.on('client.open', () => {
    wsState.value = 'connected'
    pushLog('INFO', 'ws', '通信已连接')
  })
  wsClient.on('client.close', () => {
    wsState.value = 'disconnected'
    pingMs.value = null
  })
  wsClient.on('system.hello', (msg: Envelope) => {
    const ver = (msg.data as { server_version?: string }).server_version ?? ''
    pushLog('INFO', 'ws', `后端服务已握手（v${ver}）`)
    void checkHealth()
  })
  wsClient.on('log.message', (msg: Envelope) => {
    const d = msg.data as { level?: string; message?: string; logger?: string }
    pushLog(d.level || 'INFO', d.logger || 'backend', d.message || '')
  })
  // Use actual port from supervisor status for health checks
  wsClient.on('client.open', () => {
    wsState.value = 'connected'
    pushLog('INFO', 'ws', '通信已连接')
    void checkHealth()
  })
  wsClient.on('pong', () => {
    /* keep-alive */
  })
  wsClient.on('project.open', () => void refreshProjectLabel())
  wsClient.on('project.create', () => void refreshProjectLabel())
  wsClient.on('system.hello', () => void refreshProjectLabel())
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
  const st = await api.restartBackend()
  applyBackendStatus(st)
  pushLog('INFO', 'supervisor', `后端服务状态：${st.status}`)
}

async function bootstrap(): Promise<void> {
  const saved = localStorage.getItem('yolo-vision-workbench-theme')
  applyTheme(saved === 'dark' ? 'dark' : 'light')

  const api = window.yoloStudio
  if (api) {
    api.onBackendStatus((s) => {
      applyBackendStatus(s)
      pushLog('INFO', 'supervisor', `后端服务状态：${s.status}${s.port ? ` :${s.port}` : ''}${s.message ? ` · ${s.message}` : ''}`)
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
    const wsUrl = await api.getWsUrl()
    connectWs(wsUrl)
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
  window.addEventListener('yolo-project-changed', () => void refreshProjectLabel())
})
onUnmounted(() => {
  window.removeEventListener('yolo-project-changed', () => void refreshProjectLabel())
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
  </div>
</template>
