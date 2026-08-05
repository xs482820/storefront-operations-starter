<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from '@/utils/message'

import { updateSku } from '../../api/modules'
import type { ProductSkuItem } from '../../types/api'

const props = defineProps<{
  modelValue: boolean
  sku: ProductSkuItem | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: []
}>()

const loading = defineModel<boolean>('loading', { default: false })

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const form = reactive({
  retail_price: 0,
  wholesale_price: 0,
  online_stock: 0,
  min_sale_qty: 1,
  min_wholesale_qty: 1,
  is_active: true,
})

watch(
  () => props.sku,
  (sku) => {
    if (!sku) {
      return
    }
    form.retail_price = Number(sku.retail_price)
    form.wholesale_price = Number(sku.wholesale_price)
    form.online_stock = sku.online_stock
    form.min_sale_qty = sku.min_sale_qty
    form.min_wholesale_qty = sku.min_wholesale_qty
    form.is_active = sku.is_active
  },
  { immediate: true },
)

async function submit() {
  if (!props.sku) {
    return
  }

  loading.value = true
  try {
    await updateSku(props.sku.id, { ...form })
    ElMessage.success('SKU 已更新')
    emit('success')
    visible.value = false
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" :title="sku ? `编辑 SKU · ${sku.sku_label}` : '编辑 SKU'" width="620px">
    <el-form label-position="top">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="零售价">
            <el-input-number v-model="form.retail_price" :precision="2" :min="0" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="批发价">
            <el-input-number v-model="form.wholesale_price" :precision="2" :min="0" style="width: 100%" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="线上库存">
            <el-input-number v-model="form.online_stock" :min="0" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="是否启用">
            <el-switch v-model="form.is_active" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="起售量">
            <el-input-number v-model="form.min_sale_qty" :min="1" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="起批量">
            <el-input-number v-model="form.min_wholesale_qty" :min="1" style="width: 100%" />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>
