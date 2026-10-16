<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import Icon from '../components/Icon.vue'
import { wsClient } from '../api/ws'
import { formatError } from '../utils/errors'

/** 独立摄像头预览窗口，只保留画面与最小化的窗口控制。 */
const imageUrl = ref('')
const pinned = ref(false)
const errorMsg = ref('')
const zoomMode = ref<'fit' | 'fill'>('fit')
const route = useRoute()
// 只显示发起独立窗口时指定的摄像头流，避免混入其他页面的帧。
const streamId = computed(() => String(route.query.stream_id || ''))

const imgStyle = computed(() => ({
  objectFit: (zoomMode.value === 'fill' ? 'cover' : 'contain') as 'cover' | 'contain'
}))

async function togglePin(): Promise<void> {
  pinned.value = !pinned.value
  await window.yoloStudio?.setAlwaysOnTop?.(pinned.value)
}

function toggleFullscreen(): void {
  const el = document.documentElement
  if (document.fullscreenElement) void document.exitFullscreen()
  else void el.requestFullscreen()
}

onMounted(() => {
  wsClient.on('stream.frame', (msg: { data?: Record<string, unknown> }) => {
    const d = (msg.data || {}) as { data_url?: string; stream_id?: string }
    if (!streamId.value || d.stream_id !== streamId.value) return
    if (d.data_url) imageUrl.value = d.data_url
  })
  wsClient.on('stream.error', (msg: { data?: Record<string, unknown> }) => {
    const stream = String((msg.data as { stream_id?: string })?.stream_id || '')
    if (!streamId.value || stream !== streamId.value) return
    errorMsg.value = formatError((msg.data as { message?: string })?.message || '摄像头错误')
  })
})

onUnmounted(() => {
  wsClient.close()
})
</script>

<template>
  <!-- 独立预览窗口主体只保留摄像头画面，控制按钮覆盖在画面上方。 -->
  <div class="popout">
    <div class="controls">
      <button
        type="button"
        class="control"
        :class="{ on: pinned }"
        title="置顶窗口"
        aria-label="置顶窗口"
        :aria-pressed="pinned"
        @click="togglePin"
      >
        <Icon name="pin" :size="16" />
      </button>
      <button
        type="button"
        class="control"
        :title="zoomMode === 'fit' ? '铺满窗口' : '适应窗口'"
        :aria-label="zoomMode === 'fit' ? '铺满窗口' : '适应窗口'"
        @click="zoomMode = zoomMode === 'fit' ? 'fill' : 'fit'"
      >
        {{ zoomMode === 'fit' ? '铺' : '适' }}
      </button>
      <button type="button" class="control" title="全屏" aria-label="全屏" @click="toggleFullscreen">全</button>
    </div>
    <div class="frame">
      <img v-if="imageUrl" :src="imageUrl" :style="imgStyle" alt="摄像头预览" />
      <div v-else class="empty">等待摄像头画面…</div>
      <p v-if="errorMsg" class="err">{{ errorMsg }}</p>
    </div>
  </div>
</template>

<style scoped>
.popout {
  position: relative;
  height: 100%;
  background: var(--bg-app);
  color: var(--text-primary);
}
.controls {
  position: absolute;
  z-index: 2;
  top: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  opacity: 0.2;
  transition: opacity 150ms var(--ease);
}
.popout:hover .controls,
.controls:focus-within {
  opacity: 1;
}
.control {
  min-width: 28px;
  height: 28px;
  padding: 0 7px;
  border: 1px solid color-mix(in srgb, var(--border-strong) 70%, transparent);
  border-radius: 6px;
  background: color-mix(in srgb, var(--bg-chrome) 88%, transparent);
  color: inherit;
  cursor: pointer;
}
.control:hover,
.control.on {
  color: var(--accent-ink);
  background: var(--accent-soft);
}
.frame {
  position: relative;
  width: 100%;
  height: 100%;
  background: var(--bg-canvas);
}
.frame img {
  width: 100%;
  height: 100%;
  display: block;
}
.empty {
  height: 100%;
  display: grid;
  place-items: center;
  color: var(--text-muted);
  font-size: 13px;
}
.err {
  position: absolute;
  left: 8px;
  bottom: 8px;
  color: var(--danger);
  font-size: 12px;
  margin: 0;
}
</style>
