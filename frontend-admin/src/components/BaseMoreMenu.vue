<template>
  <div class="more-menu">
    <button ref="triggerRef" type="button" class="more-trigger" @click.stop="toggleOpen">
      <span>{{ label }}</span>
      <span class="more-caret">▾</span>
    </button>

    <Teleport to="body">
      <transition name="fade-pop">
        <div v-if="open" class="more-menu-layer" @click="close">
          <div class="more-menu-panel" :style="panelStyle" @click.stop>
            <button
              v-for="item in items"
              :key="item.key"
              type="button"
              class="more-menu-item"
              :class="{ danger: item.danger, disabled: item.disabled }"
              :disabled="item.disabled"
              @click="selectItem(item)"
            >
              {{ item.label }}
            </button>
          </div>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

export interface MoreMenuItem {
  key: string
  label: string
  danger?: boolean
  disabled?: boolean
}

const props = defineProps<{
  items: MoreMenuItem[]
  label?: string
}>()

const emit = defineEmits<{
  (event: 'select', key: string): void
}>()

const open = ref(false)
const triggerRef = ref<HTMLButtonElement | null>(null)
const panelStyle = ref<Record<string, string>>({})
const menuWidth = 180

const label = computed(() => props.label || '更多')

function updatePosition() {
  const trigger = triggerRef.value
  if (!trigger) return
  const rect = trigger.getBoundingClientRect()
  const left = Math.max(8, Math.min(window.innerWidth - menuWidth - 8, rect.right - menuWidth))
  const top = Math.min(window.innerHeight - 12, rect.bottom + 8)
  panelStyle.value = {
    left: `${left}px`,
    top: `${top}px`,
    minWidth: `${menuWidth}px`,
  }
}

function openMenu() {
  open.value = true
  updatePosition()
  window.addEventListener('resize', updatePosition)
  window.addEventListener('scroll', updatePosition, true)
  window.addEventListener('keydown', onKeydown)
}

function close() {
  open.value = false
  window.removeEventListener('resize', updatePosition)
  window.removeEventListener('scroll', updatePosition, true)
  window.removeEventListener('keydown', onKeydown)
}

function toggleOpen() {
  if (open.value) {
    close()
    return
  }
  openMenu()
}

function selectItem(item: MoreMenuItem) {
  if (item.disabled) return
  emit('select', item.key)
  close()
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    close()
  }
}

onBeforeUnmount(() => {
  close()
})
</script>

<style scoped>
.more-menu {
  display: inline-flex;
  align-items: center;
}

.more-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease;
}

.more-trigger:hover {
  background: var(--bg-canvas);
  color: var(--text-primary);
  border-color: var(--border-dark);
}

.more-caret {
  font-size: 12px;
}

.more-menu-layer {
  position: fixed;
  inset: 0;
  z-index: 2000;
}

.more-menu-panel {
  position: fixed;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  box-shadow: var(--shadow-md);
}

.more-menu-item {
  min-width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  white-space: nowrap;
}

.more-menu-item:hover:not(:disabled) {
  background: var(--bg-canvas);
}

.more-menu-item.danger {
  color: var(--color-danger);
}

.more-menu-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.fade-pop-enter-active,
.fade-pop-leave-active {
  transition: opacity 0.16s ease;
}

.fade-pop-enter-from,
.fade-pop-leave-to {
  opacity: 0;
}
</style>
