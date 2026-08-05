<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from '@/utils/message'

import { bulkCreateSku } from '../../api/modules'
import { parseTextareaList } from '../../utils/format'
import type { ProductDetail } from '../../types/api'

const props = defineProps<{
  modelValue: boolean
  product: ProductDetail | null
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
  sku_type: 'retail' as 'retail' | 'wholesale',
  spec_values_1_text: '',
  spec_values_2_text: '',
  online_stock: 20,
  retail_price: 39.9,
  wholesale_price: 28.8,
  min_sale_qty: 1,
  min_wholesale_qty: 1,
  is_mixed_pack: false,
  mixed_pack_note: '',
})

watch(
  () => props.product?.supports_wholesale,
  (supportsWholesale) => {
    if (!supportsWholesale && form.sku_type === 'wholesale') {
      form.sku_type = 'retail'
    }
  },
)

async function submit() {
  if (!props.product) {
    return
  }

  const specValues1 = parseTextareaList(form.spec_values_1_text)
  const specValues2 = parseTextareaList(form.spec_values_2_text)

  if (!specValues1.length || !specValues2.length) {
    ElMessage.warning('请先填两个规格维度的取值')
    return
  }

  loading.value = true
  try {
    await bulkCreateSku({
      product_id: props.product.id,
      sku_type: form.sku_type,
      spec_values_1: specValues1,
      spec_values_2: specValues2,
      online_stock: form.online_stock,
      retail_price: form.retail_price,
      wholesale_price: form.wholesale_price,
      min_sale_qty: form.min_sale_qty,
      min_wholesale_qty: form.min_wholesale_qty,
      is_mixed_pack: form.is_mixed_pack,
      mixed_pack_note: form.mixed_pack_note || undefined,
    })
    ElMessage.success('SKU 批量生成完成')
    emit('success')
    visible.value = false
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="批量生成 SKU" width="760px">
    <div v-if="product" class="dialog-hint">
      当前商品：<strong>{{ product.name }}</strong>
      <span>{{ product.spec_dim_1_name }} × {{ product.spec_dim_2_name }}</span>
    </div>

    <el-form label-position="top">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="SKU 类型">
            <el-radio-group v-model="form.sku_type">
              <el-radio-button label="retail">零售</el-radio-button>
              <el-radio-button label="wholesale" :disabled="!product?.supports_wholesale">批发</el-radio-button>
            </el-radio-group>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="默认线上库存">
            <el-input-number v-model="form.online_stock" :min="0" :max="99999" style="width: 100%" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item :label="product?.spec_dim_1_name || '规格一'">
            <el-input
              v-model="form.spec_values_1_text"
              type="textarea"
              :rows="6"
              placeholder="一行一个，也支持逗号分隔"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item :label="product?.spec_dim_2_name || '规格二'">
            <el-input
              v-model="form.spec_values_2_text"
              type="textarea"
              :rows="6"
              placeholder="一行一个，也支持逗号分隔"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="零售价">
            <el-input-number v-model="form.retail_price" :min="0" :precision="2" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="批发价">
            <el-input-number v-model="form.wholesale_price" :min="0" :precision="2" style="width: 100%" />
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

      <el-space wrap>
        <el-checkbox v-model="form.is_mixed_pack">这是混装规格</el-checkbox>
      </el-space>

      <el-form-item label="混装说明">
        <el-input v-model="form.mixed_pack_note" placeholder="例如：整版混码，一手 5 件起批" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="submit">生成 SKU</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.dialog-hint {
  margin-bottom: 18px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(255, 239, 204, 0.66);
  color: var(--text-soft);
}

.dialog-hint strong {
  color: var(--text-main);
  margin-right: 10px;
}
</style>
