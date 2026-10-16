<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import BrandMark from './BrandMark.vue'
import {
  BUILTIN_PACKAGE_SOURCES,
  type PackageSourceId,
  type PackageSourceSelection
} from '../../shared/package-source'

interface RuntimeSetupView {
  managed: boolean
  phase: 'initializing' | 'ready' | 'failed'
  step: string
  message: string
  error: string
  details: string[]
  packageSource: PackageSourceSelection
}

const props = defineProps<{
  runtime: RuntimeSetupView
  retrying: boolean
}>()

const emit = defineEmits<{
  retryRuntime: [source: PackageSourceSelection]
}>()

// 绑定初始化弹窗节点，供键盘焦点管理复用。
const panel = ref<HTMLElement | null>(null)
// 记住弹窗打开前的焦点元素，初始化完成后恢复键盘位置。
let focusBeforeSetup: HTMLElement | null = null
// 保存用户在失败重试时选择的镜像源与自定义地址。
const selectedPackageSource = ref<PackageSourceSelection>({ ...props.runtime.packageSource })
// 展示可直接选择的国内 PyPI 镜像和自定义入口。
const packageSourceOptions: Array<{ id: PackageSourceId; label: string }> = [
  ...BUILTIN_PACKAGE_SOURCES.map(({ id, label }) => ({ id, label })),
  { id: 'custom', label: '自定义镜像' }
]
// 限定初始化弹窗只在打包版运行环境未就绪时显示。
const runtimeVisible = computed(
  () => props.runtime.managed && props.runtime.phase !== 'ready'
)
// 统一供模板和焦点管理逻辑判断弹窗可见状态。
const visible = computed(() => runtimeVisible.value)
// 标记需要展示详细错误和可编辑镜像源的失败状态。
const isRuntimeFailure = computed(() => runtimeVisible.value && props.runtime.phase === 'failed')
// 标记初始化进度动画和忙碌状态。
const isWorking = computed(() => runtimeVisible.value && props.runtime.phase === 'initializing')
// 重试过程中锁定镜像输入，避免修改与当前任务竞争。
const canEditPackageSource = computed(() => isRuntimeFailure.value && !props.retrying)
// 显示当前保存的首选镜像，便于用户确认下一次重试设置。
const selectedPackageSourceLabel = computed(() => {
  if (props.runtime.phase !== 'initializing') return ''
  if (props.runtime.packageSource.id === 'custom') return '自定义镜像'
  return packageSourceOptions.find((item) => item.id === props.runtime.packageSource.id)?.label || ''
})
// 阻止无效自定义地址提交给主进程和 pip。
const customSourceValid = computed(() => {
  if (selectedPackageSource.value.id !== 'custom') return true
  try {
    const url = new URL(selectedPackageSource.value.customUrl)
    return (url.protocol === 'https:' || url.protocol === 'http:') && Boolean(url.hostname)
  } catch {
    return false
  }
})

watch(() => props.runtime.packageSource, (source) => {
  selectedPackageSource.value = { ...source }
}, { deep: true })

// 弹层打开时将焦点移入对话框，关闭时把焦点还给此前的控件。
watch(visible, async (shown, wasShown) => {
  if (shown) {
    if (!wasShown) {
      focusBeforeSetup = document.activeElement instanceof HTMLElement ? document.activeElement : null
    }
    await nextTick()
    const firstFocusable = panel.value?.querySelector<HTMLElement>(
      'button:not(:disabled), select:not(:disabled), input:not(:disabled), summary'
    )
    ;(firstFocusable ?? panel.value)?.focus()
  } else {
    focusBeforeSetup?.focus()
    focusBeforeSetup = null
  }
}, { immediate: true })

/** 将 Tab 键焦点限制在初始化对话框内，满足模态窗口的键盘操作习惯。 */
function trapFocus(event: KeyboardEvent): void {
  if (event.key !== 'Tab' || !panel.value) return
  const items = [...panel.value.querySelectorAll<HTMLElement>(
    'button:not(:disabled), select:not(:disabled), input:not(:disabled), summary'
  )]
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
  <!-- 首次启动环境初始化反馈层，展示进度、日志、错误和重试入口。 -->
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
          <span class="setup-brand-wrap">
            <BrandMark :size="42" variant="tile" :animate="runtimeVisible && runtime.phase === 'initializing'" />
            <span
              v-if="isRuntimeFailure"
              class="setup-mark-error"
              aria-hidden="true"
            >!</span>
          </span>
          <div>
            <h1 id="startup-setup-title">首次启动初始化</h1>
            <p class="setup-subtitle">软件正在准备本机运行环境，完成后即可开始使用。</p>
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
            首次准备会安装服务依赖、CPU 版 PyTorch 和 YOLO 组件。请保持软件开启；模型权重不会自动下载，可在「模型管理」中按需下载或导入。
          </p>

          <section class="setup-source" aria-labelledby="setup-source-title">
            <div class="setup-source-heading">
              <strong id="setup-source-title">Python 包镜像源</strong>
              <span v-if="selectedPackageSourceLabel">首选：{{ selectedPackageSourceLabel }}</span>
            </div>
            <select
              id="setup-package-source"
              v-model="selectedPackageSource.id"
              :disabled="!canEditPackageSource"
              aria-label="选择 Python 包镜像源"
            >
              <option v-for="source in packageSourceOptions" :key="source.id" :value="source.id">
                {{ source.label }}
              </option>
            </select>
            <input
              v-if="selectedPackageSource.id === 'custom'"
              v-model="selectedPackageSource.customUrl"
              type="url"
              inputmode="url"
              autocomplete="url"
              placeholder="https://镜像域名/simple"
              aria-label="自定义 Python 包镜像地址"
              :disabled="!canEditPackageSource"
            />
            <p v-if="selectedPackageSource.id === 'custom' && !customSourceValid" class="setup-source-error">
              请填写有效的 http 或 https 镜像索引地址。
            </p>
            <p>
              默认使用清华镜像；安装会按当前首选源尝试，并自动回退到其他内置源。自定义地址需指向 pip simple 索引；PyTorch CPU 包同时查询官方 CPU 源和这些镜像。
            </p>
          </section>

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
            :disabled="retrying || !customSourceValid"
            @click="emit('retryRuntime', { ...selectedPackageSource })"
          >
            {{ retrying ? '正在重试…' : '保存镜像源并重试' }}
          </button>
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

.setup-brand-wrap {
  position: relative;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
}

.setup-mark-error {
  position: absolute;
  right: -5px;
  bottom: -5px;
  display: grid;
  width: 19px;
  height: 19px;
  place-items: center;
  border: 2px solid var(--bg-panel);
  border-radius: 50%;
  background: var(--danger);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
}

.setup-heading h1 {
  margin: 0;
  font-size: 22px;
  line-height: 1.25;
}

.setup-subtitle,
.setup-stage p {
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

.setup-source {
  display: grid;
  gap: 9px;
  margin-top: 18px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-inset);
}

.setup-source-heading {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 4px 12px;
}

.setup-source-heading span,
.setup-source p {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.setup-source .setup-source-error {
  color: var(--danger);
}

.setup-source select,
.setup-source input {
  width: 100%;
  min-height: 36px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--bg-panel);
  color: var(--text-primary);
  padding: 7px 9px;
  font: inherit;
}

.setup-source select:focus-visible,
.setup-source input:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.setup-source select:disabled,
.setup-source input:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.setup-source p {
  margin: 0;
  line-height: 1.5;
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
