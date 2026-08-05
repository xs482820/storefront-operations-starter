<script setup lang="ts">
import { reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from '@/utils/message'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const form = reactive({
  identifier: '',
  password: '',
})

async function submit() {
  if (!form.identifier || !form.password) {
    ElMessage.warning('请输入登录标识和口令')
    return
  }

  try {
    await auth.login({
      identifier: form.identifier,
      username: form.identifier,
      password: form.password,
    })
    ElMessage.success('登录成功')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
    router.push(redirect)
  } catch {
    // handled by interceptor
  }
}
</script>

<template>
  <div class="login-page">
    <section class="login-card glass-panel" aria-labelledby="login-title" aria-describedby="login-summary">
      <div class="login-copy">
        <p class="eyebrow">Admin Entry</p>
        <h1 id="login-title">管理后台入口</h1>
        <p id="login-summary" class="summary">仅限授权人员使用。</p>
      </div>

      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item>
          <span class="sr-only">访问标识</span>
          <el-input
            v-model="form.identifier"
            autocomplete="username"
            placeholder="访问标识"
            size="large"
            clearable
          />
        </el-form-item>

        <el-form-item>
          <span class="sr-only">安全口令</span>
          <el-input
            v-model="form.password"
            autocomplete="current-password"
            type="password"
            placeholder="安全口令"
            size="large"
          />
        </el-form-item>

        <el-button type="primary" size="large" class="submit-button" :loading="auth.loading" @click="submit">
          登录
        </el-button>
      </el-form>
    </section>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.12), transparent 28%),
    radial-gradient(circle at bottom right, rgba(220, 38, 38, 0.08), transparent 32%),
    var(--bg-canvas);
}

.login-card {
  width: min(100%, 460px);
  padding: 32px;
  border-radius: 24px;
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-md);
  background: var(--bg-surface);
}

.login-copy {
  margin-bottom: 28px;
}

.eyebrow {
  margin: 0 0 10px;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.login-copy h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.2;
  color: var(--text-primary);
}

.summary {
  margin: 12px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
  font-size: 14px;
}

.submit-button {
  width: 100%;
  margin-top: 8px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
