<template>
  <BaseDrawer v-model="open" title="个人信息" width="560px">
    <div class="profile-drawer">
      <section class="profile-summary">
        <div class="profile-avatar">
          <img v-if="avatarUrl" :src="avatarUrl" alt="头像" />
          <span v-else>{{ avatarInitial }}</span>
        </div>
        <div class="profile-summary-text">
          <h3>{{ profileDisplayName }}</h3>
          <p>{{ profileMeta }}</p>
        </div>
      </section>

      <div class="profile-tabs">
        <button :class="['tab-btn', currentTab === 'profile' ? 'active' : '']" @click="currentTab = 'profile'">
          基础资料
        </button>
        <button :class="['tab-btn', currentTab === 'password' ? 'active' : '']" @click="currentTab = 'password'">
          修改密码
        </button>
      </div>

      <section v-if="currentTab === 'profile'" class="profile-panel">
        <label class="field">
          <span>用户名</span>
          <input :value="profile?.username || '未获取'" class="input readonly-input" readonly />
        </label>

        <label class="field">
          <span>显示名称</span>
          <input v-model="profileForm.display_name" class="input" maxlength="64" placeholder="请输入显示名称" />
        </label>

        <label class="field">
          <span>头像</span>
          <ImageUploadField v-model="profileForm.avatar_url" hint="支持直接上传图片，或粘贴图片链接" />
        </label>
      </section>

      <section v-else class="profile-panel">
        <label class="field">
          <span>当前密码</span>
          <input v-model="passwordForm.current_password" class="input" type="password" placeholder="请输入当前密码" />
        </label>

        <label class="field">
          <span>新密码</span>
          <input v-model="passwordForm.new_password" class="input" type="password" placeholder="请输入新密码" />
        </label>

        <label class="field">
          <span>确认新密码</span>
          <input v-model="passwordForm.confirm_password" class="input" type="password" placeholder="再次输入新密码" />
        </label>
      </section>
    </div>

    <template #footer>
      <button class="btn-outline" @click="open = false">关闭</button>
      <button class="btn-primary" :disabled="saving" @click="saveCurrentTab">
        {{ saving ? '保存中...' : currentTab === 'profile' ? '保存资料' : '更新密码' }}
      </button>
    </template>
  </BaseDrawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import BaseDrawer from '@/components/BaseDrawer.vue'
import ImageUploadField from '@/components/shared/ImageUploadField.vue'
import { updateSelfPassword, updateSelfProfile } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from '@/utils/message'

const open = defineModel<boolean>({ required: true })

const props = defineProps<{
  initialTab?: 'profile' | 'password'
}>()

const auth = useAuthStore()
const currentTab = ref<'profile' | 'password'>('profile')
const saving = ref(false)

const profileForm = reactive({
  display_name: '',
  avatar_url: '',
})

const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

const profile = computed(() => auth.profile)
const profileDisplayName = computed(() => profileForm.display_name.trim() || profile.value?.display_name || profile.value?.username || '管理员')
const profileMeta = computed(() => {
  const role = profile.value?.role || 'admin'
  const phone = profile.value?.phone ? ` · ${profile.value.phone}` : ''
  const roleMap: Record<string, string> = {
    admin: '超级管理员',
    employee: '员工',
    retail: '零售客户',
    wholesale: '批发客户',
  }
  return `${roleMap[role] || '管理员'}${phone}`
})
const avatarUrl = computed(() => profileForm.avatar_url.trim())
const avatarInitial = computed(() => (profileDisplayName.value || '管').slice(0, 1))

watch(
  () => open.value,
  (visible) => {
    if (visible) {
      currentTab.value = props.initialTab || 'profile'
      syncFromProfile()
    } else {
      currentTab.value = 'profile'
      passwordForm.current_password = ''
      passwordForm.new_password = ''
      passwordForm.confirm_password = ''
    }
  },
)

watch(
  () => profile.value,
  () => {
    if (open.value) {
      syncFromProfile()
    }
  },
  { deep: true },
)

watch(
  () => props.initialTab,
  (tab) => {
    if (open.value) {
      currentTab.value = tab || 'profile'
    }
  },
)

function syncFromProfile() {
  profileForm.display_name = profile.value?.display_name || ''
  profileForm.avatar_url = profile.value?.avatar_url || ''
  passwordForm.current_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
}

async function saveCurrentTab() {
  if (currentTab.value === 'profile') {
    await saveProfile()
    return
  }
  await savePassword()
}

async function saveProfile() {
  saving.value = true
  try {
    await updateSelfProfile({
      display_name: profileForm.display_name.trim() || null,
      avatar_url: profileForm.avatar_url.trim() || null,
    })
    await auth.fetchProfile()
    ElMessage.success('个人资料已更新')
  } finally {
    saving.value = false
  }
}

async function savePassword() {
  if (!passwordForm.current_password.trim()) {
    ElMessage.warning('请先输入当前密码')
    return
  }
  if (!passwordForm.new_password.trim()) {
    ElMessage.warning('请先输入新密码')
    return
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  saving.value = true
  try {
    await updateSelfPassword({
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    })
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
    ElMessage.success('密码已更新')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.profile-drawer {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.profile-summary {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(220, 38, 38, 0.08), rgba(37, 99, 235, 0.06));
}

.profile-avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  flex-shrink: 0;
}

.profile-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.profile-summary-text h3 {
  margin: 0;
  font-size: 18px;
  color: var(--text-primary);
}

.profile-summary-text p {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--text-tertiary);
}

.profile-tabs {
  display: flex;
  gap: 8px;
  padding: 4px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--bg-canvas);
}

.tab-btn {
  flex: 1;
  min-height: 38px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
}

.tab-btn.active {
  background: var(--bg-surface);
  color: var(--text-primary);
  box-shadow: var(--shadow-sm);
  font-weight: 600;
}

.profile-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 14px;
  color: var(--text-secondary);
}

.field > span {
  font-weight: 600;
}

.input {
  width: 100%;
  min-height: 40px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 8px 12px;
  background: var(--bg-surface);
  color: var(--text-primary);
  box-sizing: border-box;
}

.readonly-input {
  background: var(--bg-canvas);
}

.btn-primary,
.btn-outline {
  min-width: 96px;
}
</style>
