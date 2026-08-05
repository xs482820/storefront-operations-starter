<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="modelValue" class="drawer-overlay" @click="handleClose"></div>
    </Transition>

    <Transition name="slide-right">
      <div v-if="modelValue" class="drawer-wrapper" :style="{ width }">
        <header class="drawer-header">
          <h3 class="drawer-title">{{ title }}</h3>
          <button class="btn-close" @click="handleClose">×</button>
        </header>

        <main class="drawer-body">
          <slot></slot>
        </main>

        <footer v-if="$slots.footer" class="drawer-footer">
          <slot name="footer"></slot>
        </footer>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
defineProps({
  modelValue: { type: Boolean, required: true },
  title: { type: String, default: '详情' },
  width: { type: String, default: '500px' },
})

const emit = defineEmits(['update:modelValue', 'close'])

const handleClose = () => {
  emit('update:modelValue', false)
  emit('close')
}
</script>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(17, 24, 39, 0.5);
  z-index: 1000;
}

.drawer-wrapper {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  background-color: var(--bg-surface);
  box-shadow: var(--shadow-drawer);
  display: flex;
  flex-direction: column;
  z-index: 1001;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-light);
}

.drawer-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.btn-close {
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}

.btn-close:hover {
  background: var(--bg-canvas);
  color: var(--text-primary);
}

.drawer-body {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.drawer-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--border-light);
  background-color: var(--bg-canvas);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
}
</style>
