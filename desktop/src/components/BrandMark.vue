<script setup lang="ts">
/**
 * 品牌标识（内联 SVG，随主题走）。
 * variant: 'symbol' 断角取景框 + Y（默认，用于标题栏/启动页）
 *          'tile'   带深色磁贴（用于关于页、头像位、托盘占位）
 * animate: 启动时的"描边生长 + Y 落位"（仅建议一次性播放）
 */
const props = withDefaults(
  defineProps<{
    size?: number
    variant?: 'symbol' | 'tile'
    animate?: boolean
  }>(),
  { size: 24, variant: 'symbol', animate: false }
)

const isTile = () => props.variant === 'tile'
</script>

<template>
  <!-- 使用内联矢量形状渲染可缩放的产品标识。 -->
  <svg
    class="brand-mark"
    :class="{ 'is-animated': animate }"
    :width="size"
    :height="size"
    viewBox="0 0 128 128"
    fill="none"
    aria-hidden="true"
  >
    <defs>
      <linearGradient id="bm-ink" gradientUnits="userSpaceOnUse" x1="6" y1="6" x2="46.6" y2="122">
        <stop offset="0" stop-color="#1b2532" />
        <stop offset="1" stop-color="#0c121b" />
      </linearGradient>
      <linearGradient id="bm-amber" gradientUnits="userSpaceOnUse" x1="22" y1="12" x2="102" y2="112">
        <stop offset="0" stop-color="#ffc247" />
        <stop offset="1" stop-color="#f29311" />
      </linearGradient>
    </defs>

    <template v-if="isTile()">
      <rect x="6" y="6" width="116" height="116" rx="30" fill="url(#bm-ink)" />
      <rect
        x="6.75"
        y="6.75"
        width="114.5"
        height="114.5"
        rx="29.25"
        stroke="#ffffff"
        stroke-opacity="0.09"
        stroke-width="1.5"
      />
    </template>

    <!-- 断角取景框 -->
    <g :stroke="isTile() ? '#a7b8cc' : 'var(--text-secondary)'" stroke-width="10" stroke-linecap="round">
      <path class="bm-br bm-br-1" d="M24 58 V 40 Q 24 24 40 24 H 58" />
      <path class="bm-br bm-br-2" d="M104 70 V 88 Q 104 104 88 104 H 70" />
    </g>

    <!-- 品牌字母 Y -->
    <g class="bm-y" stroke="url(#bm-amber)" stroke-width="12" stroke-linecap="round" stroke-linejoin="round">
      <path d="M45 40 L64 61 L83 40 M64 61 L64 88" />
    </g>
  </svg>
</template>

<style scoped>
.brand-mark {
  display: block;
  flex-shrink: 0;
}

.is-animated .bm-br {
  stroke-dasharray: 78;
  stroke-dashoffset: 78;
  animation: bm-draw 0.55s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

.is-animated .bm-br-2 {
  animation-delay: 0.16s;
}

.is-animated .bm-y {
  opacity: 0;
  transform-origin: 64px 64px;
  transform: scale(0.92);
  animation: bm-settle 0.5s cubic-bezier(0.22, 1, 0.36, 1) 0.42s forwards;
}

@keyframes bm-draw {
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes bm-settle {
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .is-animated .bm-br,
  .is-animated .bm-y {
    animation: none;
    stroke-dashoffset: 0;
    opacity: 1;
    transform: none;
  }
}
</style>
