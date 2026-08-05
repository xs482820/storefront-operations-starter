<template>
  <div class="base-list-toolbar">
    <div class="toolbar-left">
      <slot name="left"></slot>
    </div>

    <div class="toolbar-right">
      <div class="search-box">
        <span class="search-icon">⌕</span>
        <input
          type="text"
          class="search-input"
          :placeholder="placeholder"
          :value="modelValue"
          @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
          @keyup.enter="$emit('search')"
        />
      </div>

      <select
        v-if="sortOptions.length > 0"
        class="sort-select"
        :value="currentSort"
        @change="$emit('update:currentSort', ($event.target as HTMLSelectElement).value); $emit('sort-change')"
      >
        <option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </option>
      </select>

      <slot name="right"></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '搜索...' },
  currentSort: { type: String, default: '' },
  sortOptions: {
    type: Array as () => Array<{ label: string; value: string }>,
    default: () => [],
  },
})

defineEmits(['update:modelValue', 'update:currentSort', 'search', 'sort-change'])
</script>

<style scoped>
.base-list-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-light);
}

.toolbar-left { display: flex; gap: 8px; align-items: center; }
.toolbar-right { display: flex; gap: 12px; align-items: center; }

.search-box {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 10px;
  font-size: 14px;
  color: var(--text-tertiary);
}

.search-input {
  width: 220px;
  padding: 8px 12px 8px 32px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 13px;
  outline: none;
  background: var(--bg-surface);
  color: var(--text-primary);
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.search-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.1);
}

.sort-select {
  padding: 8px 12px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 13px;
  outline: none;
  background-color: var(--bg-surface);
  color: var(--text-primary);
  cursor: pointer;
}

.sort-select:focus { border-color: var(--color-primary); }
</style>
