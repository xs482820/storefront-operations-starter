<template>
  <header class="app-page-header">
    <div>
      <h1>{{ title }}</h1>
      <p v-if="description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="header-actions"><slot name="actions" /></div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<style scoped>
.app-page-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; }
h1 { margin: 0; color: var(--text-primary); font-size: 25px; font-weight: 700; line-height: 1.2; letter-spacing: 0; }
p { margin: 8px 0 0; color: var(--text-secondary); font-size: 13px; line-height: 1.5; }
.header-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
</style>
