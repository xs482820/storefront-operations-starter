<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { fetchStockLogs } from '../../api/modules'
import { formatDateTime } from '../../utils/format'
import type { ProductSkuItem, StockLogItem } from '../../types/api'

const props = defineProps<{
  modelValue: boolean
  sku: ProductSkuItem | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const loading = ref(false)
const logs = ref<StockLogItem[]>([])

async function load() {
  if (!props.sku) {
    logs.value = []
    return
  }

  loading.value = true
  try {
    const response = await fetchStockLogs(props.sku.id)
    logs.value = response.data
  } finally {
    loading.value = false
  }
}

watch(() => props.sku?.id, load, { immediate: true })
</script>

<template>
  <el-drawer v-model="visible" :title="sku ? `库存日志 · ${sku.sku_label}` : '库存日志'" size="48%">
    <el-table :data="logs" v-loading="loading" stripe>
      <el-table-column prop="created_at" label="时间" min-width="160">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column prop="reason" label="原因" min-width="120" />
      <el-table-column prop="delta_qty" label="变化量" min-width="90" />
      <el-table-column prop="before_qty" label="变更前" min-width="90" />
      <el-table-column prop="after_qty" label="变更后" min-width="90" />
      <el-table-column prop="ref_order_no" label="关联订单" min-width="150" />
      <el-table-column prop="note" label="备注" min-width="180" />
    </el-table>
  </el-drawer>
</template>
