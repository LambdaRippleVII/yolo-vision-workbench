<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Icon from '../components/Icon.vue'
import { wsClient } from '../api/ws'
import { formatError } from '../utils/errors'

/** 独立摄像头预览窗口，只保留画面与最小化的窗口控制。 */
const imageUrl = ref('')
const pinned = ref(false)
const errorMsg = ref('')
const zoomMode = ref<'fit' | 'fill'>('fit')

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
    const d = (msg.data || {}) as { data_url?: string }
    if (d.data_url) imageUrl.value = d.data_url
  })
  wsClient.on('stream.error', (msg: { data?: Record<string, unknown> }) => {
    errorMsg.value = formatError((msg.data as { message?: string })?.message || '摄像头错误')
  })
})

onUnmounted(() => {
  wsClient.close()
})
</script>

<template>
  <!-- 独立预览窗口主体，保持画面占满可用区域。 -->
  <div class="popout">
    <div class="bar">
      <button
        type="button"
        class="ghost"
        :class="{ on: pinned }"
        :title="'图钉置顶'"
        :aria-label="'图钉置顶'"
        :aria-pressed="pinned"
        @click="togglePin"
      >
        <Icon name="pin" :size="16" />
      </button>
      <button type="button" class="ghost" @click="zoomMode = zoomMode === 'fit' ? 'fill' : 'fit'">
        {{ zoomMode === 'fit' ? '适应窗口' : '铺满窗口' }}
      </button>
      <button type="button" class="ghost" @click="toggleFullscreen">全屏</button>
      <span class="spacer" />
      <span class="hint">摄像头画面</span>
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
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-app);
  color: var(--text-primary);
}
.bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: var(--bg-chrome);
  border-bottom: 1px solid var(--border);
  -webkit-app-region: drag;
  flex: 0 0 36px;
}
.bar button {
  -webkit-app-region: no-drag;
  color: inherit;
  border-color: transparent;
  background: transparent;
}
.bar button.on {
  color: var(--accent-ink);
}
.spacer {
  flex: 1;
}
.hint {
  font-size: 11px;
  opacity: 0.7;
}
.frame {
  flex: 1;
  min-height: 0;
  position: relative;
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
