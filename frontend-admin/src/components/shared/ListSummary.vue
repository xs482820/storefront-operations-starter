<template>
  <div class="list-summary" aria-label="列表摘要">
    <span v-for="item in items" :key="item.label" :class="item.tone ? `is-${item.tone}` : ''">
      <strong>{{ item.value }}</strong>{{ item.label }}
    </span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  items: Array<{ label: string; value: number; tone?: 'warning' | 'danger' }>
}>()
</script>

<style scoped>
.list-summary { display: flex; align-items: center; gap: 0; color: var(--text-tertiary); font-size: 13px; white-space: nowrap; }
.list-summary span { padding: 0 10px; border-left: 1px solid var(--border-light); }
.list-summary span:first-child { padding-left: 0; border-left: 0; }
.list-summary strong { margin-right: 3px; color: var(--text-primary); font-variant-numeric: tabular-nums; }
.list-summary .is-warning strong { color: var(--el-color-warning); }
.list-summary .is-danger strong { color: var(--el-color-danger); }
</style>
