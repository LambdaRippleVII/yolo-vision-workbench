<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

interface RuntimeSetupView {
  managed: boolean
  phase: 'initializing' | 'ready' | 'failed'
  step: string
  message: string
  error: string
  details: string[]
}

interface ModelSetupView {
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

const props = defineProps<{
  runtime: RuntimeSetupView
  models: ModelSetupView
  retrying: boolean
}>()

const emit = defineEmits<{
  retryRuntime: []
  retryModels: []
  retryModel: [modelId: string]
  continue: []
}>()

const panel = ref<HTMLElement | null>(null)
let focusBeforeSetup: HTMLElement | null = null
const runtimeVisible = computed(
  () => props.runtime.managed && props.runtime.phase !== 'ready'
)
const visible = computed(() => runtimeVisible.value || props.models.visible)
const isRuntimeFailure = computed(() => runtimeVisible.value && props.runtime.phase === 'failed')
const isWorking = computed(
  () =>
    (runtimeVisible.value && props.runtime.phase === 'initializing') ||
    props.models.phase === 'checking' ||
    props.models.phase === 'downloading'
)

watch(visible, async (shown, wasShown) => {
  if (shown) {
    if (!wasShown) {
      focusBeforeSetup = document.activeElement instanceof HTMLElement ? document.activeElement : null
    }
    await nextTick()
    const firstFocusable = panel.value?.querySelector<HTMLElement>('button:not(:disabled), summary')
    ;(firstFocusable ?? panel.value)?.focus()
  } else {
    focusBeforeSetup?.focus()
    focusBeforeSetup = null
  }
}, { immediate: true })

function trapFocus(event: KeyboardEvent): void {
  if (event.key !== 'Tab' || !panel.value) return
  const items = [...panel.value.querySelectorAll<HTMLElement>('button:not(:disabled), summary')]
  if (!items.length) {
    event.preventDefault()
    panel.value.focus()
    return
  }
  const first = items[0]
  const last = items[items.length - 1]
  if (document.activeElement === panel.value) {
    event.preventDefault()
    ;(event.shiftKey ? last : first).focus()
  } else if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}
</script>

<template>
  <Transition name="setup-fade">
    <div v-if="visible" class="setup-backdrop" :class="{ 'setup-backdrop-error': isRuntimeFailure }">
      <section
        ref="panel"
        class="setup-panel"
        :aria-busy="isWorking"
        aria-labelledby="startup-setup-title"
        role="dialog"
        aria-modal="true"
        tabindex="-1"
        @keydown="trapFocus"
      >
        <div class="setup-heading">
          <span class="setup-mark" :class="{ failed: isRuntimeFailure }" aria-hidden="true">
            {{ isRuntimeFailure || models.phase === 'failed' ? '!' : 'Y' }}
          </span>
          <div>
            <h1 id="startup-setup-title">{{ runtimeVisible ? '首次启动初始化' : '准备内置模型' }}</h1>
            <p class="setup-subtitle">
              {{
                runtimeVisible
                  ? '软件正在准备本机运行环境，完成后即可开始使用。'
                  : '正在下载可用模型权重；此步骤只下载文件，不会自动开始推理。'
              }}
            </p>
          </div>
        </div>

        <template v-if="runtimeVisible">
          <div class="setup-stage">
            <div class="setup-stage-row">
              <strong>{{ runtime.step }}</strong>
              <span v-if="runtime.phase === 'initializing'" class="setup-working">进行中</span>
              <span v-else class="setup-failed">需要处理</span>
            </div>
            <p>{{ runtime.message }}</p>
            <div v-if="runtime.phase === 'initializing'" class="setup-progress" aria-hidden="true">
              <span />
            </div>
          </div>

          <p class="setup-note">
            首次准备需要联网下载服务依赖、CPU 版 PyTorch 和 YOLO 组件。请保持软件开启；安装文件保存在当前用户目录。
          </p>

          <div v-if="runtime.phase === 'failed'" class="setup-error" role="alert">
            <strong>初始化失败</strong>
            <pre>{{ runtime.error || '没有收到详细错误信息。' }}</pre>
            <details v-if="runtime.details.length">
              <summary>查看安装日志</summary>
              <pre class="setup-log">{{ runtime.details.join('\n') }}</pre>
            </details>
          </div>

          <button
            v-if="runtime.phase === 'failed'"
            type="button"
            class="primary setup-primary"
            :disabled="retrying"
            @click="emit('retryRuntime')"
          >
            {{ retrying ? '正在重试…' : '重试初始化' }}
          </button>
        </template>

        <template v-else>
          <p class="setup-model-message">{{ models.message }}</p>
          <div v-if="models.phase === 'checking' || models.phase === 'downloading'" class="setup-progress" aria-hidden="true">
            <span />
          </div>
          <ul v-if="models.models.length" class="setup-model-list">
            <li v-for="model in models.models" :key="model.model_id">
              <div class="setup-model-copy">
                <strong>{{ model.name }}</strong>
                <span v-if="model.state === 'downloading'">{{ models.message }}</span>
                <span v-else-if="model.state === 'failed'" class="setup-failed">{{ model.error }}</span>
                <span v-else-if="model.state === 'ready'" class="setup-working">已就绪</span>
                <span v-else>等待下载</span>
              </div>
              <button
                v-if="model.state === 'failed'"
                type="button"
                :disabled="retrying || models.phase === 'downloading'"
                @click="emit('retryModel', model.model_id)"
              >
                重试
              </button>
            </li>
          </ul>
          <div v-if="models.phase === 'failed'" class="setup-model-help" role="alert">
            下载失败时可检查网络或代理后重试；也可以在「模型管理」中补下，或导入本地权重。
          </div>
          <p v-if="models.phase === 'complete'" class="setup-success" role="status">
            内置模型已准备完成。选择模型并点击「开始推理」后才会进行识别。
          </p>
          <div class="setup-actions">
            <button
              v-if="models.phase === 'failed'"
              type="button"
              :disabled="retrying"
              @click="emit('retryModels')"
            >
              {{ retrying ? '正在重试…' : '重试失败模型' }}
            </button>
            <button type="button" class="primary" @click="emit('continue')">
              {{ models.phase === 'complete' ? '开始使用' : '稍后处理' }}
            </button>
          </div>
        </template>
      </section>
    </div>
  </Transition>
</template>

<style scoped>
.setup-backdrop {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: grid;
  place-items: center;
  padding: 24px;
  overflow: auto;
  background: color-mix(in srgb, var(--bg-app) 94%, #15202e 6%);
}

.setup-backdrop-error {
  background: color-mix(in srgb, var(--bg-app) 88%, var(--danger) 12%);
}

.setup-panel {
  width: min(720px, 100%);
  max-height: min(86vh, 860px);
  overflow: auto;
  padding: 28px;
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  background: var(--bg-panel);
  color: var(--text-primary);
  box-shadow: var(--shadow-md);
}

.setup-heading {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.setup-mark {
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: var(--accent);
  color: var(--text-inverse);
  font-size: 18px;
  font-weight: 700;
}

.setup-mark.failed {
  background: var(--danger);
}

.setup-heading h1 {
  margin: 0;
  font-size: 22px;
  line-height: 1.25;
}

.setup-subtitle,
.setup-stage p,
.setup-model-message {
  margin: 7px 0 0;
  color: var(--text-secondary);
}

.setup-stage {
  margin-top: 24px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-inset);
}

.setup-stage-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.setup-working {
  color: var(--success);
}

.setup-failed {
  color: var(--danger);
}

.setup-progress {
  height: 5px;
  margin-top: 14px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--border);
}

.setup-progress span {
  display: block;
  width: 36%;
  height: 100%;
  border-radius: inherit;
  background: var(--accent);
  animation: setup-progress 1.4s var(--ease) infinite alternate;
}

.setup-note,
.setup-model-help {
  margin: 14px 0 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.setup-error {
  margin-top: 18px;
  padding: 14px;
  border: 1px solid color-mix(in srgb, var(--danger) 35%, var(--border));
  border-radius: var(--radius-lg);
  background: var(--danger-soft);
  color: var(--text-primary);
}

.setup-error pre,
.setup-log {
  max-height: 180px;
  overflow: auto;
  margin: 8px 0 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--text-secondary);
  font: 12px/1.5 var(--font-mono);
}

.setup-error summary {
  margin-top: 12px;
  cursor: pointer;
  color: var(--text-primary);
}

.setup-primary {
  margin-top: 18px;
}

.setup-model-message {
  margin-top: 22px;
}

.setup-model-list {
  display: grid;
  gap: 8px;
  max-height: 42vh;
  overflow: auto;
  margin: 16px 0 0;
  padding: 0;
  list-style: none;
}

.setup-model-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}

.setup-model-copy {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.setup-model-copy span {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  overflow-wrap: anywhere;
}

.setup-model-help {
  color: var(--danger);
}

.setup-success {
  margin: 16px 0 0;
  color: var(--success);
}

.setup-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}

.setup-fade-enter-active,
.setup-fade-leave-active {
  transition: opacity var(--dur-mid) var(--ease);
}

.setup-fade-enter-from,
.setup-fade-leave-to {
  opacity: 0;
}

@keyframes setup-progress {
  from {
    transform: translateX(-15%);
  }
  to {
    transform: translateX(205%);
  }
}

@media (prefers-reduced-motion: reduce) {
  .setup-progress span {
    animation: none;
    width: 100%;
  }
}
</style>
