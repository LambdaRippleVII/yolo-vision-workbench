<script setup lang="ts">
/** Simple confirmation modal for export-with-edits. */
defineProps<{
  visible: boolean
  title: string
  message: string
  confirmText?: string
}>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()
</script>

<template>
  <div v-if="visible" class="mask" @click.self="emit('cancel')">
    <div class="dialog" role="dialog">
      <h3 class="title">{{ title }}</h3>
      <p class="msg">{{ message }}</p>
      <div class="actions">
        <button type="button" @click="emit('cancel')">取消</button>
        <button type="button" class="primary" @click="emit('confirm')">
          {{ confirmText || '确定' }}
        </button>
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
  z-index: 1000;
}
.dialog {
  width: min(420px, 90vw);
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 20px;
  box-shadow: var(--shadow-md);
}
.title {
  margin: 0 0 8px;
  font-size: var(--text-lg);
}
.msg {
  margin: 0 0 16px;
  color: var(--text-secondary);
  font-size: var(--text-md);
  line-height: 1.5;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
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
