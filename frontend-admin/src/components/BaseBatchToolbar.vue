<template>
  <div v-if="selectedCount > 0" class="batch-toolbar">
    <div class="batch-summary">
      <span class="batch-count">
        已选择 <strong>{{ selectedCount }}</strong> 项
      </span>
      <button type="button" class="batch-clear" @click="$emit('clear')">清空</button>
      <span v-if="hint" class="batch-hint">{{ hint }}</span>
    </div>

    <div class="batch-actions">
      <slot name="prepend"></slot>

      <button
        v-for="action in actions"
        :key="action.key"
        type="button"
        class="batch-action-btn"
        :class="{ danger: action.danger }"
        :disabled="action.disabled"
        @click="$emit('action', action.key)"
      >
        {{ action.label }}
      </button>

      <slot></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
export interface BatchActionItem {
  key: string
  label: string
  danger?: boolean
  disabled?: boolean
}

defineProps<{
  selectedCount: number
  hint?: string
  actions?: BatchActionItem[]
}>()

defineEmits<{
  (event: 'action', key: string): void
  (event: 'clear'): void
}>()
</script>

<style scoped>
.batch-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-light);
  background: var(--bg-table-header);
}

.batch-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  color: var(--text-secondary);
}

.batch-count {
  font-size: 14px;
  color: var(--text-primary);
  white-space: nowrap;
}

.batch-count strong {
  color: var(--color-primary);
}

.batch-clear {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0;
  white-space: nowrap;
}

.batch-clear:hover {
  color: var(--color-primary);
}

.batch-hint {
  font-size: 13px;
  color: var(--text-tertiary);
}

.batch-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.batch-action-btn {
  min-height: 34px;
  padding: 0 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease;
}

.batch-action-btn:hover:not(:disabled) {
  background: var(--bg-canvas);
  color: var(--text-primary);
  border-color: var(--border-dark);
}

.batch-action-btn.danger {
  color: var(--color-danger);
}

.batch-action-btn.danger:hover:not(:disabled) {
  border-color: rgba(220, 38, 38, 0.45);
  background: rgba(220, 38, 38, 0.06);
}

.batch-action-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
