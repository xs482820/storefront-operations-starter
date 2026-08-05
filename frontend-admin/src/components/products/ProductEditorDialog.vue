<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from '@/utils/message'

import { createProduct, updateProduct } from '../../api/modules'
import type { CreateProductPayload, ProductDetail } from '../../types/api'

const props = defineProps<{
  modelValue: boolean
  product?: ProductDetail | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: []
}>()

const loading = defineModel<boolean>('loading', { default: false })

const isEdit = computed(() => Boolean(props.product))
const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const form = reactive<CreateProductPayload & { is_active?: boolean }>({
  name: '',
  product_code: '',
  model_name: '',
  brand: '',
  category: '',
  description: '',
  spec_dim_1_name: '颜色/形状',
  spec_dim_2_name: '尺码/大小',
  supports_retail: true,
  supports_wholesale: false,
  has_dual_price: true,
  is_active: true,
})

watch(
  () => props.product,
  (value) => {
    if (!value) {
      Object.assign(form, {
        name: '',
        product_code: '',
        model_name: '',
        brand: '',
        category: '',
        description: '',
        spec_dim_1_name: '颜色/形状',
        spec_dim_2_name: '尺码/大小',
        supports_retail: true,
        supports_wholesale: false,
        has_dual_price: true,
        is_active: true,
      })
      return
    }

    Object.assign(form, {
      name: value.name,
      product_code: value.product_code,
      model_name: value.model_name || '',
      brand: value.brand || '',
      category: value.category || '',
      description: value.description || '',
      spec_dim_1_name: value.spec_dim_1_name,
      spec_dim_2_name: value.spec_dim_2_name,
      supports_retail: value.supports_retail,
      supports_wholesale: value.supports_wholesale,
      has_dual_price: value.has_dual_price,
      is_active: value.is_active,
    })
  },
  { immediate: true },
)

async function submit() {
  loading.value = true
  try {
    if (props.product) {
      await updateProduct(props.product.id, form)
      ElMessage.success('商品已更新')
    } else {
      await createProduct(form)
      ElMessage.success('商品已创建')
    }
    emit('success')
    visible.value = false
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" :title="isEdit ? '编辑商品' : '新建商品'" width="760px">
    <el-form label-position="top">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="商品名称">
            <el-input v-model="form.name" placeholder="例如：春秋包脚裤" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="商品编码">
            <el-input v-model="form.product_code" :disabled="isEdit" placeholder="例如：KZ-2401" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="型号">
            <el-input v-model="form.model_name" placeholder="例如：A17" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="分类">
            <el-input v-model="form.category" placeholder="例如：婴童裤装" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="规格维度一">
            <el-input v-model="form.spec_dim_1_name" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="规格维度二">
            <el-input v-model="form.spec_dim_2_name" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="品牌">
        <el-input v-model="form.brand" />
      </el-form-item>

      <el-form-item label="商品说明">
        <el-input v-model="form.description" type="textarea" :rows="3" />
      </el-form-item>

      <el-space wrap>
        <el-checkbox v-model="form.supports_retail">支持零售</el-checkbox>
        <el-checkbox v-model="form.supports_wholesale">支持批发</el-checkbox>
        <el-checkbox v-model="form.has_dual_price">启用双价</el-checkbox>
        <el-checkbox v-model="form.is_active">启用商品</el-checkbox>
      </el-space>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="submit">保存商品</el-button>
    </template>
  </el-dialog>
</template>
