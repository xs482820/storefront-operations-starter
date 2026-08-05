<template>
  <div class="notify-root" aria-live="polite" aria-atomic="true">
    <TransitionGroup name="notify-drop" tag="div" class="notify-stack">
      <div
        v-for="item in items"
        :key="item.id"
        :class="['notify-item', `is-${item.type}`]"
        @click="remove(item.id)"
      >
        <span class="notify-dot"></span>
        <span class="notify-text">{{ item.text }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { useAppMessages } from '@/utils/message'

const { items, remove } = useAppMessages()
</script>

<style scoped>
.notify-root {
  position: fixed;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 3000;
  pointer-events: none;
}

.notify-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
}

.notify-item {
  min-width: 220px;
  max-width: min(560px, calc(100vw - 32px));
  padding: 10px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  background: var(--bg-surface);
  color: var(--text-primary);
  box-shadow: var(--shadow-md);
  display: flex;
  align-items: center;
  gap: 8px;
  pointer-events: auto;
  cursor: pointer;
}

.notify-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-tertiary);
  flex: 0 0 7px;
}

.notify-text {
  font-size: 13px;
  line-height: 1.4;
  word-break: break-word;
}

.notify-item.is-success .notify-dot { background: var(--color-success); }
.notify-item.is-error .notify-dot { background: var(--color-danger); }
.notify-item.is-warning .notify-dot { background: var(--color-warning); }
.notify-item.is-info .notify-dot { background: #2563eb; }

.notify-drop-enter-active,
.notify-drop-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.notify-drop-enter-from {
  opacity: 0;
  transform: translateY(-14px) scale(0.98);
}

.notify-drop-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.98);
}

.notify-drop-move {
  transition: transform 0.2s ease;
}
</style>

