<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import {
  defaultLabelSettings,
  defaultLabelStyle,
  fillTemplate,
  type LabelItem,
  type LabelPos,
  type LabelSettings,
  type TextRotate
} from './labelTypes'

const props = defineProps<{
  visible: boolean
  modelValue: LabelSettings
}>()

const emit = defineEmits<{
  'update:visible': [boolean]
  'update:modelValue': [LabelSettings]
  apply: [LabelSettings]
}>()

const local = reactive<LabelSettings>(defaultLabelSettings())
const activeId = ref('')
const showStyleFor = ref<string | null>(null)

function ensureRotate(s: { rotate?: TextRotate }): void {
  if (s.rotate === undefined) s.rotate = 0
}

watch(
  () => props.visible,
  (v) => {
    if (!v) return
    const src = props.modelValue || defaultLabelSettings()
    local.mode = src.mode || 'auto'
    local.autoTemplate = src.autoTemplate || '{id}:{display}'
    local.autoStyle = { ...defaultLabelStyle(), ...(src.autoStyle || {}) }
    ensureRotate(local.autoStyle)
    if (local.autoStyle.bgEnabled === undefined) local.autoStyle.bgEnabled = true
    local.labels = JSON.parse(JSON.stringify(src.labels?.length ? src.labels : defaultLabelSettings().labels))
    for (const item of local.labels) {
      ensureRotate(item.style)
      if (item.style.bgEnabled === undefined) item.style.bgEnabled = true
    }
    local.box = { ...local.box, ...(src.box || {}) }
    activeId.value = local.labels[0]?.id || ''
    showStyleFor.value = null
  },
  { immediate: true }
)

const sampleObj = {
  id: 1,
  class_name: 'person',
  display_name: '人员',
  class_id: 0,
  confidence: 0.95,
  model_id: 'coco',
  track_id: null
}

const placeholders = [
  { key: '{id}', label: 'ID' },
  { key: '{display}', label: '显示名' },
  { key: '{class}', label: '原始类名' },
  { key: '{class_id}', label: '类别ID' },
  { key: '{confidence}', label: '置信度' },
  { key: '{model_id}', label: '模型' },
  { key: '{track_id}', label: '跟踪ID' }
]

const rotateOptions: Array<{ value: TextRotate; label: string }> = [
  { value: 0, label: '0°' },
  { value: 90, label: '90°' },
  { value: 180, label: '180°' },
  { value: 270, label: '270°' }
]

const posText: Record<LabelPos, string> = {
  top: '上',
  bottom: '下',
  left: '左',
  right: '右'
}

function hasPlace(place: LabelPos): boolean {
  return local.labels.some((x) => x.place === place)
}

function addLabel(place: LabelPos): void {
  if (hasPlace(place)) return
  const item: LabelItem = {
    id: `l_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    place,
    template: place === 'top' ? '{id}:{display}' : '{confidence}',
    style: defaultLabelStyle()
  }
  local.labels.push(item)
  activeId.value = item.id
}

function removeLabel(id: string): void {
  const i = local.labels.findIndex((x) => x.id === id)
  if (i >= 0) local.labels.splice(i, 1)
  if (activeId.value === id) activeId.value = local.labels[0]?.id || ''
}

function insertPh(key: string): void {
  const item = local.labels.find((x) => x.id === activeId.value)
  if (!item) return
  item.template = (item.template || '') + key
}

function onPreviewLabelClick(id: string): void {
  activeId.value = id
  const el = document.getElementById(`label-card-${id}`)
  el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

function posTransform(place: LabelPos, rotate: number): string {
  if (place === 'top') return `translateX(-50%) rotate(${rotate}deg)`
  if (place === 'bottom') return `translateX(-50%) rotate(${rotate}deg)`
  if (place === 'left') return `translateY(-50%) rotate(${rotate}deg)`
  return `translateY(-50%) rotate(${rotate}deg)`
}

function sampleText(tpl: string): string {
  return fillTemplate(tpl, sampleObj)
}

const activeItem = computed(() => local.labels.find((x) => x.id === activeId.value) || null)

function apply(): void {
  const next: LabelSettings = JSON.parse(JSON.stringify(local))
  emit('update:modelValue', next)
  emit('apply', next)
  emit('update:visible', false)
}
</script>

<template>
  <!-- 编辑检测框标签、文字样式和类别颜色，并提供实时画布预览。 -->
  <div v-if="visible" class="mask">
    <div class="dialog wide">
      <div class="dialog-head">
        <div>
          <h3 class="title">标签配置</h3>
          <p class="subtitle">左侧预览 · 右侧编辑 · 点击标签可定位</p>
        </div>
        <button type="button" class="ghost icon-x" title="关闭" @click="emit('update:visible', false)">×</button>
      </div>

      <div class="layout">
        <!-- 左侧：标签预览 -->
        <div class="preview-col">
          <div class="sec">预览（点击标签可定位编辑）</div>
          <div class="preview-stage">
            <div class="demo-box" :style="{ border: `${local.box.lineWidth}px solid ${local.box.color}` }">
              <!-- 自动模式：只展示顶部标签 -->
              <div
                v-if="local.mode === 'auto'"
                class="demo-label top"
                :style="{
                  background: local.autoStyle.bgEnabled === false ? 'transparent' : local.autoStyle.bg,
                  color: local.autoStyle.color,
                  fontSize: local.autoStyle.fontSize + 'px',
                  fontWeight: local.autoStyle.bold ? 600 : 400,
                  transform: `translateX(-50%) rotate(${local.autoStyle.rotate || 0}deg)`,
                  textShadow: local.autoStyle.bgEnabled === false ? '0 1px 3px rgba(0,0,0,.55)' : 'none'
                }"
              >
                {{ sampleText(local.autoTemplate) }}
              </div>
              <div
                v-for="item in local.labels"
                v-else
                :key="item.id"
                class="demo-label"
                :class="[item.place, { active: item.id === activeId }]"
                :style="{
                  background: item.style.bgEnabled === false ? 'transparent' : item.style.bg,
                  color: item.style.color,
                  fontSize: item.style.fontSize + 'px',
                  fontWeight: item.style.bold ? 600 : 400,
                  transform: posTransform(item.place, item.style.rotate || 0),
                  textShadow: item.style.bgEnabled === false ? '0 1px 3px rgba(0,0,0,.55)' : 'none'
                }"
                @click.stop="onPreviewLabelClick(item.id)"
              >
                {{ sampleText(item.template) }}
              </div>
            </div>
          </div>
          <div class="box-style-row">
            <span>检测框粗细</span>
            <input v-model.number="local.box.lineWidth" type="number" min="1" max="8" class="num" />
            <span class="hint-inline">类别颜色请在「模型管理」中设置</span>
          </div>
        </div>

        <!-- 右侧：样式编辑器 -->
        <div class="edit-col">
          <div class="sec">位置模式</div>
          <div class="mode-row">
            <label>
              <input v-model="local.mode" type="radio" value="auto" />
              自动（默认上方，空间不够时换边）
            </label>
            <label>
              <input v-model="local.mode" type="radio" value="manual" />
              手动（可多个标签）
            </label>
          </div>

          <template v-if="local.mode === 'auto'">
            <div class="sec">自动标签模板</div>
            <input v-model="local.autoTemplate" class="tpl" />
            <div class="ph-row">
              <button
                v-for="p in placeholders"
                :key="p.key"
                type="button"
                class="ph"
                @click="local.autoTemplate += p.key"
              >
                +{{ p.label }}
              </button>
            </div>
            <div class="row-actions">
              <button type="button" class="ghost" @click="showStyleFor = 'auto'">字体/颜色…</button>
            </div>
          </template>

          <template v-else>
            <div class="sec">添加标签位置（每边最多 1 个）</div>
            <div class="add-row">
              <button
                v-for="p in ['top', 'bottom', 'left', 'right'] as LabelPos[]"
                :key="p"
                type="button"
                :disabled="hasPlace(p)"
                @click="addLabel(p)"
              >
                + {{ posText[p] }}侧
              </button>
            </div>

            <div class="sec">标签列表</div>
            <div class="cards">
              <div
                v-for="item in local.labels"
                :id="`label-card-${item.id}`"
                :key="item.id"
                class="card"
                :class="{ active: item.id === activeId }"
                @click="activeId = item.id"
              >
                <div class="card-head">
                  <span class="badge">{{ posText[item.place] }}侧</span>
                  <input v-model="item.template" class="tpl" />
                  <button type="button" class="ghost mini" @click.stop="showStyleFor = item.id">样式</button>
                  <button type="button" class="ghost mini" @click.stop="removeLabel(item.id)">删</button>
                </div>
                <div v-if="item.id === activeId" class="ph-row">
                  <button
                    v-for="p in placeholders"
                    :key="p.key"
                    type="button"
                    class="ph"
                    @click.stop="activeId = item.id; insertPh(p.key)"
                  >
                    +{{ p.label }}
                  </button>
                </div>
                <div class="preview-text">→ {{ sampleText(item.template) }}</div>
              </div>
              <div v-if="!local.labels.length" class="muted">点上方「+ 上侧」等添加标签（每边限 1 个）</div>
              <div v-else class="muted">同一位置仅允许一个标签，可删除后更换</div>
            </div>
          </template>
        </div>
      </div>

      <div class="actions">
        <button type="button" @click="emit('update:visible', false)">取消</button>
        <button type="button" class="primary" @click="apply">应用</button>
      </div>

      <!-- 嵌套样式选择浮层 -->
      <div v-if="showStyleFor" class="style-mask" @click.self="showStyleFor = null">
        <div class="style-dialog">
          <h4>标签字体与颜色</h4>
          <template v-if="showStyleFor === 'auto'">
            <div class="style-grid">
              <label>字号</label>
              <input v-model.number="local.autoStyle.fontSize" type="number" min="10" max="28" />
              <label>文字色</label>
              <input v-model="local.autoStyle.color" type="color" class="color" />
              <label>底色</label>
              <div class="bg-row">
                <label class="chk"><input v-model="local.autoStyle.bgEnabled" type="checkbox" /> 使用底色</label>
                <input
                  v-model="local.autoStyle.bg"
                  type="color"
                  class="color"
                  :disabled="local.autoStyle.bgEnabled === false"
                />
              </div>
              <label>旋转</label>
              <div class="rot-row">
                <button
                  v-for="r in rotateOptions"
                  :key="r.value"
                  type="button"
                  class="rot"
                  :class="{ on: (local.autoStyle.rotate || 0) === r.value }"
                  @click="local.autoStyle.rotate = r.value"
                >
                  {{ r.label }}
                </button>
              </div>
              <label>加粗</label>
              <input v-model="local.autoStyle.bold" type="checkbox" />
            </div>
          </template>
          <template v-else-if="activeItem">
            <div class="style-grid">
              <label>字号</label>
              <input v-model.number="activeItem.style.fontSize" type="number" min="10" max="28" />
              <label>文字色</label>
              <input v-model="activeItem.style.color" type="color" class="color" />
              <label>底色</label>
              <div class="bg-row">
                <label class="chk"><input v-model="activeItem.style.bgEnabled" type="checkbox" /> 使用底色</label>
                <input
                  v-model="activeItem.style.bg"
                  type="color"
                  class="color"
                  :disabled="activeItem.style.bgEnabled === false"
                />
              </div>
              <label>旋转</label>
              <div class="rot-row">
                <button
                  v-for="r in rotateOptions"
                  :key="r.value"
                  type="button"
                  class="rot"
                  :class="{ on: (activeItem.style.rotate || 0) === r.value }"
                  @click="activeItem.style.rotate = r.value"
                >
                  {{ r.label }}
                </button>
              </div>
              <label>加粗</label>
              <input v-model="activeItem.style.bold" type="checkbox" />
            </div>
          </template>
          <div class="actions">
            <button type="button" class="primary" @click="showStyleFor = null">完成</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  background: rgba(20, 28, 40, 0.35);
  display: grid;
  place-items: center;
  z-index: 1200;
}
.dialog.wide {
  width: 860px;
  height: 560px;
  overflow: hidden;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 0;
  box-shadow: var(--shadow-md);
  position: relative;
  display: flex;
  flex-direction: column;
}
.dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 22px 8px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-panel);
  border-radius: 16px 16px 0 0;
}
.title {
  margin: 0;
  font-size: 18px;
  font-weight: 650;
}
.subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}
.icon-x {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  font-size: 18px;
}
.layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 0;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.preview-col {
  border-right: 1px solid var(--border);
  padding: 16px 18px;
  overflow: auto;
  background: color-mix(in srgb, var(--bg-workspace) 70%, var(--bg-panel));
}
.edit-col {
  padding: 12px 18px;
  overflow: auto;
}
.preview-stage {
  min-height: 280px;
  background: var(--bg-workspace);
  border: 1px solid var(--border);
  border-radius: 12px;
  display: grid;
  place-items: center;
  padding: 28px;
}
.demo-box {
  position: relative;
  width: 180px;
  height: 130px;
}
.demo-label {
  position: absolute;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
  cursor: pointer;
}
.demo-label.active {
  outline: 2px solid var(--accent);
}
.demo-label.top {
  left: 50%;
  transform: translateX(-50%);
  bottom: 100%;
  margin-bottom: 4px;
}
.demo-label.bottom {
  left: 50%;
  transform: translateX(-50%);
  top: 100%;
  margin-top: 4px;
}
.demo-label.left {
  right: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-right: 4px;
}
.demo-label.right {
  left: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-left: 4px;
}
.box-style-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  font-size: var(--text-sm);
}
.hint-inline {
  color: var(--text-muted);
  font-size: 11px;
}
.mode-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: var(--text-sm);
}
.add-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tpl {
  width: 100%;
  height: 30px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0 8px;
  background: var(--bg-inset);
  color: var(--text-primary);
}
.ph-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0;
}
.ph {
  padding: 3px 8px;
  font-size: 11px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg-inset);
}
.cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow: auto;
}
.card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px 10px;
  background: var(--bg-inset);
}
.card.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.card-head {
  display: flex;
  gap: 6px;
  align-items: center;
}
.card-head .tpl {
  flex: 1;
}
.preview-text {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-muted);
}
.mini {
  padding: 2px 6px;
  font-size: 11px;
}
.color {
  width: 48px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.num {
  width: 56px;
  height: 28px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0 6px;
  background: var(--bg-inset);
  color: var(--text-primary);
}
.row-actions {
  margin-top: 8px;
}
.muted {
  color: var(--text-muted);
  font-size: var(--text-sm);
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 18px;
  border-top: 1px solid var(--border);
  background: var(--bg-panel);
  border-radius: 0 0 16px 16px;
}
.rot-row {
  display: flex;
  gap: 6px;
}
.rot {
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-panel);
  font-size: 12px;
}
.rot.on {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}
.bg-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.chk {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  white-space: nowrap;
}
.style-mask {
  position: absolute;
  inset: 0;
  background: rgba(20, 28, 40, 0.25);
  display: grid;
  place-items: center;
  z-index: 5;
  border-radius: var(--radius-xl);
}
.style-dialog {
  width: 320px;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  box-shadow: var(--shadow-md);
}
.style-dialog h4 {
  margin: 0 0 12px;
}
.style-grid {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px;
  align-items: center;
  font-size: var(--text-sm);
}
.style-grid input[type='number'] {
  height: 28px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0 8px;
  background: var(--bg-inset);
  color: var(--text-primary);
}

.dialog,
.style-dialog {
  animation: dialog-pop 260ms var(--spring) both;
}
@keyframes dialog-pop {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
</style>
