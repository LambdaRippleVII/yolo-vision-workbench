<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  fillTemplate,
  type LabelSettings,
  defaultLabelSettings
} from './labelTypes'

export interface BoxObject {
  id: number
  model_id: string
  class_id: number
  class_name: string
  display_name: string
  confidence: number
  geom_type: string
  geom: { bbox?: number[] }
  visible?: boolean
  style?: { color?: string; line_width?: number }
  track_id?: number | null
}

export type { LabelSettings, LabelItem, LabelPos } from './labelTypes'

const props = defineProps<{
  imageUrl: string
  objects: BoxObject[]
  selectedId?: number | null
  labelTemplate?: string
  labelSettings?: LabelSettings
}>()

const emit = defineEmits<{ select: [id: number] }>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const wrapRef = ref<HTMLDivElement | null>(null)
const img = new Image()
let ro: ResizeObserver | null = null

const zoom = ref(1)
const panX = ref(0)
const panY = ref(0)
const panning = ref(false)
let panStartX = 0
let panStartY = 0
let panOriginX = 0
let panOriginY = 0

function settings(): LabelSettings {
  if (props.labelSettings) return props.labelSettings
  const s = defaultLabelSettings()
  if (props.labelTemplate) s.autoTemplate = props.labelTemplate
  return s
}

function draw(): void {
  const canvas = canvasRef.value
  const wrap = wrapRef.value
  if (!canvas || !wrap || !img.complete || !img.naturalWidth) return

  const wrapW = wrap.clientWidth
  const wrapH = wrap.clientHeight
  const base = Math.min(wrapW / img.naturalWidth, wrapH / img.naturalHeight, 1)
  const scale = base * zoom.value
  const dw = img.naturalWidth * scale
  const dh = img.naturalHeight * scale
  const ox = (wrapW - dw) / 2 + panX.value
  const oy = (wrapH - dh) / 2 + panY.value

  const dpr = window.devicePixelRatio || 1
  canvas.width = wrapW * dpr
  canvas.height = wrapH * dpr
  canvas.style.width = wrapW + 'px'
  canvas.style.height = wrapH + 'px'

  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, wrapW, wrapH)
  ctx.drawImage(img, ox, oy, dw, dh)

  const st = settings()

  for (const o of props.objects) {
    if (o.visible === false) continue
    const bbox = o.geom?.bbox
    if (!bbox || bbox.length < 4) continue
    const [x1, y1, x2, y2] = bbox
    const rx = ox + x1 * scale
    const ry = oy + y1 * scale
    const rw = (x2 - x1) * scale
    const rh = (y2 - y1) * scale
    const selected = props.selectedId === o.id
    const boxColor = o.style?.color || st.box.color
    ctx.lineWidth = selected ? st.box.lineWidth + 2 : st.box.lineWidth
    ctx.strokeStyle = boxColor
    ctx.strokeRect(rx, ry, rw, rh)

    const modelOffset = ((o.model_id || '').split('').reduce((a, c) => a + c.charCodeAt(0), 0) % 3) * 18
    const drawTag = (
      place: 'top' | 'bottom' | 'left' | 'right',
      text: string,
      style: {
        color: string
        bg: string
        bgEnabled?: boolean
        fontSize: number
        bold: boolean
        rotate?: number
      },
      fallbackBg?: string
    ) => {
      if (!text) return
      const font = `${style.bold ? '600 ' : ''}${style.fontSize}px "Segoe UI","Microsoft YaHei",sans-serif`
      ctx.font = font
      const tw = ctx.measureText(text).width + 10
      const th = style.fontSize + 8
      let tx = rx
      let ty = ry - th - 2
      if (place === 'bottom') {
        tx = rx
        ty = ry + rh + 2
      } else if (place === 'left') {
        tx = rx - tw - 2
        ty = ry + rh / 2 - th / 2
      } else if (place === 'right') {
        tx = rx + rw + 2
        ty = ry + rh / 2 - th / 2
      } else {
        ty = ry - th - 2
        if (ty < 0) ty = ry + rh + 2
      }

      const rot = ((style.rotate || 0) * Math.PI) / 180
      const cx = tx + tw / 2
      const cy = ty + th / 2
      const useBg = style.bgEnabled !== false
      ctx.save()
      ctx.translate(cx, cy)
      ctx.rotate(rot)
      ctx.translate(-cx, -cy)
      if (useBg) {
        ctx.fillStyle = fallbackBg || o.style?.color || style.bg || '#2F6FED'
        ctx.fillRect(tx, ty, tw, th)
      }
      ctx.fillStyle = style.color
      ctx.textBaseline = 'middle'
      // slight shadow when no bg for readability
      if (!useBg) {
        ctx.shadowColor = 'rgba(0,0,0,0.55)'
        ctx.shadowBlur = 2
      }
      ctx.fillText(text, tx + 5, ty + th / 2)
      ctx.restore()
    }

    if (st.mode === 'auto') {
      drawTag('top', fillTemplate(st.autoTemplate, o), st.autoStyle, o.style?.color)
    } else {
      for (const item of st.labels) {
        drawTag(item.place, fillTemplate(item.template, o), item.style, o.style?.color)
      }
    }
  }
}

function onWheel(ev: WheelEvent): void {
  if (!ev.ctrlKey && !ev.metaKey) return
  ev.preventDefault()
  const dir = ev.deltaY > 0 ? -1 : 1
  zoom.value = Math.min(8, Math.max(0.2, zoom.value * (dir > 0 ? 1.1 : 1 / 1.1)))
  draw()
}

function onPointerDown(ev: MouseEvent): void {
  if (ev.button !== 1) return
  ev.preventDefault()
  panning.value = true
  panStartX = ev.clientX
  panStartY = ev.clientY
  panOriginX = panX.value
  panOriginY = panY.value
}

function onPointerMove(ev: MouseEvent): void {
  if (!panning.value) return
  panX.value = panOriginX + (ev.clientX - panStartX)
  panY.value = panOriginY + (ev.clientY - panStartY)
  draw()
}

function onPointerUp(ev: MouseEvent): void {
  if (ev.button === 1) panning.value = false
}

function onDblClick(): void {
  zoom.value = 1
  panX.value = 0
  panY.value = 0
  draw()
}

function onClick(ev: MouseEvent): void {
  const wrap = wrapRef.value
  if (!wrap || !img.complete) return
  const rect = wrap.getBoundingClientRect()
  const wrapW = rect.width
  const wrapH = rect.height
  const base = Math.min(wrapW / img.naturalWidth, wrapH / img.naturalHeight, 1)
  const scale = base * zoom.value
  const ox = (wrapW - img.naturalWidth * scale) / 2 + panX.value
  const oy = (wrapH - img.naturalHeight * scale) / 2 + panY.value
  const ix = (ev.clientX - rect.left - ox) / scale
  const iy = (ev.clientY - rect.top - oy) / scale

  for (const o of [...props.objects].reverse()) {
    if (o.visible === false) continue
    const bbox = o.geom?.bbox
    if (!bbox || bbox.length < 4) continue
    const [x1, y1, x2, y2] = bbox
    if (ix >= x1 && ix <= x2 && iy >= y1 && iy <= y2) {
      emit('select', o.id)
      return
    }
  }
}

watch(
  () => props.imageUrl,
  (url) => {
    zoom.value = 1
    panX.value = 0
    panY.value = 0
    img.onload = () => draw()
    img.src = url
  },
  { immediate: true }
)
watch(() => props.objects, () => draw(), { deep: true })
watch(() => props.selectedId, () => draw())
watch(() => props.labelTemplate, () => draw())
watch(() => props.labelSettings, () => draw(), { deep: true })

onMounted(() => {
  ro = new ResizeObserver(() => draw())
  if (wrapRef.value) {
    ro.observe(wrapRef.value)
    wrapRef.value.addEventListener('wheel', onWheel, { passive: false })
    wrapRef.value.addEventListener('dblclick', onDblClick)
    wrapRef.value.addEventListener('mousedown', onPointerDown)
    wrapRef.value.addEventListener('mousemove', onPointerMove)
    wrapRef.value.addEventListener('auxclick', (e) => e.preventDefault())
    window.addEventListener('mouseup', onPointerUp)
  }
})
onBeforeUnmount(() => {
  ro?.disconnect()
  if (wrapRef.value) {
    wrapRef.value.removeEventListener('wheel', onWheel)
    wrapRef.value.removeEventListener('dblclick', onDblClick)
    wrapRef.value.removeEventListener('mousedown', onPointerDown)
    wrapRef.value.removeEventListener('mousemove', onPointerMove)
  }
  window.removeEventListener('mouseup', onPointerUp)
})

defineExpose({ zoomLevel: computed(() => zoom.value) })
</script>

<template>
  <div
    ref="wrapRef"
    class="canvas-wrap"
    :class="{ panning }"
    :title="`中键拖动 · Ctrl+滚轮缩放 ${Math.round(zoom * 100)}%`"
    @click="onClick"
  >
    <canvas ref="canvasRef" />
    <div class="zoom-hint num">{{ Math.round(zoom * 100) }}%</div>
  </div>
</template>

<style scoped>
.canvas-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 320px;
  background: var(--bg-canvas);
  border-radius: var(--radius-lg);
  overflow: hidden;
  cursor: crosshair;
}
.canvas-wrap.panning {
  cursor: grabbing;
}
canvas {
  display: block;
}
.zoom-hint {
  position: absolute;
  right: 10px;
  bottom: 10px;
  background: rgba(28, 36, 48, 0.65);
  color: #fff;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  pointer-events: none;
}
</style>
