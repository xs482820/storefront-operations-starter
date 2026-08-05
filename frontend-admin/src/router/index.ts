import { createRouter, createWebHistory } from 'vue-router'

import AdminLayout from '../layouts/AdminLayout.vue'
import { useAuthStore } from '../stores/auth'

const LoginView = () => import('../views/LoginView.vue')
const DashboardView = () => import('../views/DashboardView.vue')
const ProductListView = () => import('../views/products/ProductListView.vue')
const OrderWorkbenchView = () => import('../views/orders/OrderWorkbenchView.vue')
const AftersaleWorkbenchView = () => import('../views/aftersales/AftersaleWorkbenchView.vue')
const StorefrontManagementView = () => import('../views/storefront/StorefrontManagementView.vue')
const UserManagementView = () => import('../views/users/UserManagementView.vue')
const OperationRecordsView = () => import('../views/OperationRecordsView.vue')
const AiWorkspaceView = () => import('../views/AiWorkspaceView.vue')
const PrintJobsView = () => import('../views/PrintJobsView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { public: true },
    },
    {
      path: '/',
      component: AdminLayout,
      children: [
        { path: '', redirect: '/dashboard' },
        { path: '/dashboard', name: 'dashboard', component: DashboardView },
        { path: '/products', name: 'products', component: ProductListView },
        { path: '/orders', name: 'orders', component: OrderWorkbenchView },
        { path: '/aftersales', name: 'aftersales', component: AftersaleWorkbenchView },
        { path: '/wholesale-applications', name: 'wholesale-applications', redirect: { name: 'users', query: { tab: 'pending' } } },
        { path: '/storefront', name: 'storefront', component: StorefrontManagementView },
        { path: '/users', name: 'users', component: UserManagementView},
        { path: '/operation-records', name: 'operation-records', component: OperationRecordsView },
        { path: '/print-jobs', name: 'print-jobs', component: PrintJobsView },
        { path: '/ai-workspace', name: 'ai-workspace', component: AiWorkspaceView },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.public) {
    if (to.path === '/login' && auth.isAuthenticated) {
      try {
        if (!auth.hasProfile) {
          await auth.fetchProfile()
        }
        return '/dashboard'
      } catch {
        auth.logout()
        return true
      }
    }
    return true
  }

  if (!auth.isAuthenticated) {
    return `/login?redirect=${encodeURIComponent(to.fullPath)}`
  }

  if (!auth.hasProfile) {
    try {
      await auth.fetchProfile()
    } catch {
      auth.logout()
      return `/login?redirect=${encodeURIComponent(to.fullPath)}`
    }
  }

  return true
})

export default router
