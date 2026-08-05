<template>
  <div class="base-pagination">
    <div class="page-info text-tertiary">
      共 <span class="font-bold text-primary">{{ total }}</span> 条数据
    </div>

    <div class="page-controls">
      <select class="page-size-select" :value="pageSize" @change="handleSizeChange">
        <option v-for="size in pageSizes" :key="size" :value="size">{{ size }} 条 / 页</option>
      </select>

      <div class="btn-group">
        <button class="page-btn" :disabled="currentPage <= 1" @click="handlePageChange(currentPage - 1)">上一页</button>
        <div class="current-page-display">{{ currentPage }} / {{ totalPages }}</div>
        <button class="page-btn" :disabled="currentPage >= totalPages" @click="handlePageChange(currentPage + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps({
  total: { type: Number, required: true },
  currentPage: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  pageSizes: { type: Array as () => number[], default: () => [10, 20, 50, 100] }
})

const emit = defineEmits(['update:currentPage', 'update:pageSize', 'change'])

const totalPages = computed(() => Math.ceil(props.total / props.pageSize) || 1)

const handlePageChange = (newPage: number) => {
  if (newPage >= 1 && newPage <= totalPages.value) {
    emit('update:currentPage', newPage)
    emit('change') // 触发重新拉取数据的事件
  }
}

const handleSizeChange = (e: Event) => {
  const newSize = Number((e.target as HTMLSelectElement).value)
  emit('update:pageSize', newSize)
  emit('update:currentPage', 1) // 切换条数时，自动回到第一页
  emit('change')
}
</script>

<style scoped>
.base-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: var(--bg-surface);
  border-top: 1px solid var(--border-light);
}

.page-info { font-size: 13px; }
.text-tertiary { color: var(--text-tertiary); }
.text-primary { color: var(--text-primary); }
.font-bold { font-weight: 600; }

.page-controls { display: flex; align-items: center; gap: 16px; }

.page-size-select {
  padding: 6px 10px; border: 1px solid var(--border-light);
  border-radius: var(--radius-sm); font-size: 13px; outline: none;
  background: var(--bg-surface); color: var(--text-primary); /* 改成变量 */
}
.btn-group { display: flex; align-items: center; border: 1px solid var(--border-light); border-radius: var(--radius-sm); overflow: hidden; }
.page-btn { 
  background: var(--bg-surface); /* 改成变量 */
  border: none; padding: 6px 12px; font-size: 13px; color: var(--text-secondary); cursor: pointer; transition: background 0.2s; 
}
.page-btn:hover:not(:disabled) { background: var(--bg-sidebar-hover); color: var(--text-primary); }
.page-btn:disabled { color: var(--text-tertiary); cursor: not-allowed; background: transparent; }
.current-page-display { 
  padding: 6px 16px; font-size: 13px; border-left: 1px solid var(--border-light); 
  border-right: 1px solid var(--border-light); 
  background: var(--bg-table-header); /* 改成变量 */
  color: var(--text-primary); font-weight: 500; 
}
</style>