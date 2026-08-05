<template>
  <div class="admin-layout">
    <aside class="sidebar" :class="{ 'is-collapsed': isCollapsed }">
      <div class="sidebar-header">
        <div class="logo-box">
          <span v-if="!isCollapsed" class="logo-text">门店经营助手<small>管理后台</small></span>
          <span v-else class="logo-text-mini">店</span>
        </div>
        <button class="collapse-btn" @click="toggleSidebar">
          <el-icon :size="16"><Fold v-if="!isCollapsed" /><Expand v-else /></el-icon>
        </button>
      </div>

      <nav class="sidebar-nav">
        <router-link to="/dashboard" class="nav-item" active-class="active">
          <el-icon class="nav-icon"><Histogram /></el-icon>
          <span v-if="!isCollapsed" class="nav-label">今日处理</span>
        </router-link>

        <router-link to="/orders" class="nav-item" active-class="active">
          <el-icon class="nav-icon"><Document /></el-icon>
          <span v-if="!isCollapsed" class="nav-label">订单与交接</span>
        </router-link>

        <router-link to="/products" class="nav-item" active-class="active">
          <el-icon class="nav-icon"><Goods /></el-icon>
          <span v-if="!isCollapsed" class="nav-label">商品与价格</span>
        </router-link>

        <router-link to="/users" class="nav-item" :class="{ active: isUsersSection }" active-class="">
          <el-icon class="nav-icon"><UserFilled /></el-icon>
          <span v-if="!isCollapsed" class="nav-label">客户与审核</span>
        </router-link>

        <router-link to="/aftersales" class="nav-item" active-class="active">
          <el-icon class="nav-icon"><Refresh /></el-icon>
          <span v-if="!isCollapsed" class="nav-label">售后处理</span>
        </router-link>

        <router-link to="/operation-records" class="nav-item" active-class="active">
          <el-icon class="nav-icon"><Tickets /></el-icon>
          <span v-if="!isCollapsed" class="nav-label">操作记录</span>
        </router-link>

        <router-link to="/print-jobs" class="nav-item" active-class="active">
          <el-icon class="nav-icon"><Printer /></el-icon>
          <span v-if="!isCollapsed" class="nav-label">打印任务</span>
        </router-link>

        <router-link to="/ai-workspace" class="nav-item" active-class="active">
          <el-icon class="nav-icon"><PictureRounded /></el-icon>
          <span v-if="!isCollapsed" class="nav-label">图片工作台</span>
        </router-link>

        <router-link to="/storefront" class="nav-item" active-class="active">
          <el-icon class="nav-icon"><Shop /></el-icon>
          <span v-if="!isCollapsed" class="nav-label">经营设置</span>
        </router-link>
      </nav>
    </aside>

    <main class="main-container">
      <header class="top-header">
        <div class="page-location">
          <span class="location-kicker">内部经营台</span>
          <span class="current-page">{{ currentRouteName }}</span>
        </div>

        <div class="header-actions">
          <button class="header-icon-btn" title="打开图片工作台" @click="openAiWorkspace">
            <el-icon :size="18"><PictureRounded /></el-icon>
          </button>

          <button class="theme-toggle-btn" @click="toggleTheme" title="切换白天/黑夜模式">
            <el-icon :size="18"><Moon v-if="isDark" /><Sunny v-else /></el-icon>
          </button>

          <div class="user-profile" v-click-outside="closeDropdown">
            <button class="profile-trigger" type="button" @click="toggleDropdown">
              <span class="admin-name">{{ profileDisplayName }}</span>
              <div class="avatar">
                <img v-if="profileAvatarUrl" :src="profileAvatarUrl" :alt="profileDisplayName" />
                <span v-else>{{ profileAvatarInitial }}</span>
              </div>
              <span class="arrow-down">▾</span>
            </button>

            <transition name="fade-slide">
              <div v-if="showDropdown" class="profile-dropdown" @click.stop>
                <div class="dropdown-header">
                  <div class="profile-summary">
                    <div class="profile-summary-avatar">
                      <img v-if="profileAvatarUrl" :src="profileAvatarUrl" :alt="profileDisplayName" />
                      <span v-else>{{ profileAvatarInitial }}</span>
                    </div>
                    <div class="profile-summary-copy">
                      <div class="font-bold text-primary">{{ profileDisplayName }}</div>
                      <div class="text-xs text-tertiary">{{ profileRoleLabel }}</div>
                    </div>
                  </div>
                </div>
                <div class="dropdown-divider"></div>
                <button class="dropdown-item" type="button" @click="() => openProfileDrawer()">编辑个人信息</button>
                <button class="dropdown-item" type="button" @click="() => openProfileDrawer('password')">修改密码</button>
                <button class="dropdown-item text-danger" type="button" @click="handleLogout">退出登录</button>
              </div>
            </transition>
          </div>
        </div>
      </header>

      <div class="content-wrapper">
        <router-view />
      </div>

      <AdminProfileDrawer v-model="isProfileDrawerOpen" :initial-tab="profileDrawerTab" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Histogram, Goods, Document, Refresh, UserFilled, Shop, Tickets, Printer, Fold, Expand, Moon, Sunny, PictureRounded } from '@element-plus/icons-vue'
import AdminProfileDrawer from '@/components/admin/AdminProfileDrawer.vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const currentRouteName = computed(() => {
  const nameMap: Record<string, string> = {
    dashboard: '今日处理',
    products: '商品与价格',
    storefront: '经营设置',
    orders: '订单与交接',
    'wholesale-applications': '客户与审核',
    aftersales: '售后处理',
    users: '客户与审核',
    'operation-records': '操作记录',
    'print-jobs': '打印任务',
    'ai-workspace': '图片工作台',
  }
  return nameMap[route.name as string] || '工作台'
})

const isUsersSection = computed(() =>
  route.name === 'users' || route.name === 'wholesale-applications',
)

const isCollapsed = ref(false)
const toggleSidebar = () => {
  isCollapsed.value = !isCollapsed.value
}

const isDark = ref(false)
const toggleTheme = () => {
  isDark.value = !isDark.value
  if (isDark.value) {
    document.documentElement.classList.add('dark')
    localStorage.setItem('theme', 'dark')
  } else {
    document.documentElement.classList.remove('dark')
    localStorage.setItem('theme', 'light')
  }
}

onMounted(() => {
  const savedTheme = localStorage.getItem('theme')
  if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    isDark.value = true
    document.documentElement.classList.add('dark')
  }
})

const profile = computed(() => auth.profile)
const profileDisplayName = computed(() => profile.value?.display_name || profile.value?.username || '管理员老板')
const profileRoleLabel = computed(() => {
  const role = profile.value?.role || 'admin'
  const roleMap: Record<string, string> = {
    admin: '超级管理员',
    employee: '员工',
    retail: '零售客户',
    wholesale: '批发客户',
  }
  return roleMap[role] || '管理员'
})
const profileAvatarUrl = computed(() => profile.value?.avatar_url || '')
const profileAvatarInitial = computed(() => profileDisplayName.value.slice(0, 1))

const showDropdown = ref(false)
const toggleDropdown = () => {
  showDropdown.value = !showDropdown.value
}
const closeDropdown = () => {
  showDropdown.value = false
}

const isProfileDrawerOpen = ref(false)
const profileDrawerTab = ref<'profile' | 'password'>('profile')

function openProfileDrawer(tab: 'profile' | 'password' = 'profile') {
  profileDrawerTab.value = tab
  isProfileDrawerOpen.value = true
  showDropdown.value = false
}

function openAiWorkspace() {
  router.push('/ai-workspace')
}

const handleLogout = () => {
  if (confirm('确定要退出登录吗？')) {
    auth.logout()
    router.push('/login')
  }
}

const vClickOutside = {
  mounted(el: HTMLElement, binding: { value: () => void }) {
    const handler = (event: Event) => {
      const target = event.target as Node | null
      if (target && el !== target && !el.contains(target)) {
        binding.value()
      }
    }
    ;(el as HTMLElement & { clickOutsideEvent?: (event: Event) => void }).clickOutsideEvent = handler
    document.body.addEventListener('click', handler)
  },
  unmounted(el: HTMLElement) {
    const handler = (el as HTMLElement & { clickOutsideEvent?: (event: Event) => void }).clickOutsideEvent
    if (handler) {
      document.body.removeEventListener('click', handler)
    }
  },
}
</script>

<style scoped>
.admin-layout { display: flex; height: 100vh; width: 100vw; overflow: hidden; }
.sidebar {
  width: 220px;
  background-color: var(--bg-sidebar);
  color: var(--text-sidebar);
  display: flex;
  flex-direction: column;
  transition: width 0.24s ease, background-color 0.24s ease;
  border-right: 1px solid var(--border-light);
  z-index: 20;
}
.sidebar.is-collapsed { width: 68px; }
.sidebar-header {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--border-light);
}
.logo-text { display: grid; gap: 3px; color: var(--text-primary); font-size: 17px; font-weight: 700; letter-spacing: 0; }
.logo-text small { color: var(--text-tertiary); font-size: 11px; font-weight: 500; }
.logo-text-mini { font-weight: bold; color: var(--text-primary); font-size: 20px; width: 100%; text-align: center; }
.collapse-btn { background: transparent; border: none; color: var(--text-sidebar); cursor: pointer; padding: 4px; border-radius: var(--radius-sm); }
.collapse-btn:hover { background-color: var(--bg-sidebar-hover); color: var(--text-primary); }
.sidebar-nav { padding: 16px 8px; display: flex; flex-direction: column; gap: 4px; }
.nav-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  text-decoration: none;
  color: var(--text-sidebar);
  border-radius: var(--radius-md);
  transition: background-color 0.18s ease, color 0.18s ease;
  white-space: nowrap;
}
.nav-item:hover { background-color: var(--bg-sidebar-hover); color: var(--text-primary); }
.nav-item.active { background-color: #16776f; color: var(--text-sidebar-active); font-weight: 600; }
.nav-icon { font-size: 20px; margin-right: 12px; display: inline-flex; justify-content: center; align-items: center; width: 24px; height: 24px; flex-shrink: 0; color: inherit; }
.nav-icon :deep(svg) { width: 20px; height: 20px; }
.is-collapsed .nav-icon { margin-right: 0; width: 100%; }
.nav-item.active .nav-icon { color: inherit; }
.main-container { flex: 1; display: flex; flex-direction: column; background-color: var(--bg-canvas); min-width: 0; }
.top-header {
  height: 64px;
  background-color: var(--bg-surface);
  border-bottom: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: var(--shadow-sm);
  z-index: 10;
  transition: background-color 0.24s ease;
}
.page-location { display: flex; align-items: baseline; gap: 10px; }
.location-kicker { color: var(--text-tertiary); font-size: 12px; }
.current-page { color: var(--text-primary); font-size: 15px; font-weight: 650; }
.text-tertiary { color: var(--text-tertiary); }
.header-actions { display: flex; align-items: center; gap: 20px; }
.header-icon-btn,
.theme-toggle-btn {
  background: var(--bg-canvas);
  border: 1px solid var(--border-light);
  border-radius: 50%;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 16px;
  color: var(--text-primary);
  transition: background-color 0.18s ease, border-color 0.18s ease;
}
.header-icon-btn:hover,
.theme-toggle-btn:hover { background: var(--border-light); }
.user-profile { position: relative; cursor: pointer; }
.profile-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  transition: background-color 0.18s ease;
  cursor: pointer;
}
.profile-trigger:hover { background: var(--bg-canvas); }
.admin-name { font-size: 14px; color: var(--text-secondary); font-weight: 500; }
.avatar {
  width: 32px;
  height: 32px;
  background: var(--color-primary);
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.arrow-down { font-size: 12px; color: var(--text-tertiary); }
.profile-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 240px;
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  z-index: 100;
  overflow: hidden;
}
.dropdown-header { padding: 16px; background: var(--bg-canvas); }
.profile-summary { display: flex; align-items: center; gap: 12px; }
.profile-summary-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  flex-shrink: 0;
}
.profile-summary-avatar img { width: 100%; height: 100%; object-fit: cover; }
.text-xs { font-size: 12px; }
.dropdown-divider { height: 1px; background: var(--border-light); }
.dropdown-item {
  display: block;
  width: 100%;
  padding: 12px 16px;
  border: none;
  background: transparent;
  font-size: 14px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background-color 0.18s ease;
  text-align: left;
}
.dropdown-item:hover { background: var(--bg-canvas); }
.dropdown-item.text-danger { color: var(--color-danger); }
.fade-slide-enter-active, .fade-slide-leave-active { transition: opacity 0.18s ease, transform 0.18s ease; }
.fade-slide-enter-from, .fade-slide-leave-to { opacity: 0; transform: translateY(-8px); }
.content-wrapper { flex: 1; padding: 24px; overflow-y: auto; }
</style>
