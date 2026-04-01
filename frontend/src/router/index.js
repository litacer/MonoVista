import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/pages/HomeView.vue'
import WorkspaceView from '@/pages/WorkspaceView.vue'
import AuthView from '@/pages/AuthView.vue'
import ProfileView from '@/pages/ProfileView.vue'
import AdminLayout from '@/components/AdminLayout.vue'
import AdminDashboard from '@/pages/AdminDashboard.vue'
import AdminConversions from '@/pages/AdminConversions.vue'
import AdminAuditLogs from '@/pages/AdminAuditLogs.vue'
import AdminModelRegistry from '@/pages/AdminModelRegistry.vue'
import AdminAnnouncements from '@/pages/AdminAnnouncements.vue'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/', name: 'home', component: HomeView },

  { path: '/auth/login', name: 'login', component: AuthView, meta: { authMode: 'login' } },
  { path: '/auth/register', name: 'register', component: AuthView, meta: { authMode: 'register' } },
  { path: '/auth/forgot', name: 'forgot', component: AuthView, meta: { authMode: 'forgot' } },

  // 分享预览页：无需登录，任何人可访问
  { path: '/share/:token', name: 'share', component: () => import('@/pages/ShareView.vue') },

  { path: '/workspace', name: 'workspace', component: WorkspaceView, meta: { requiresAuth: true } },
  { path: '/profile', name: 'profile', component: ProfileView, meta: { requiresAuth: true } },

  {
    path: '/admin',
    component: AdminLayout,
    meta: { requiresAuth: true, requiresAdmin: true },
    children: [
      { path: '', redirect: '/admin/dashboard' },
      { path: 'dashboard', name: 'AdminDashboard', component: AdminDashboard, meta: { title: '首页' } },
      { path: 'conversions', name: 'AdminConversions', component: AdminConversions, meta: { title: '转换管理' } },
      { path: 'audit', name: 'AdminAuditLogs', component: AdminAuditLogs, meta: { title: '用户审计' } },
      { path: 'model-registry', name: 'AdminModelRegistry', component: AdminModelRegistry, meta: { title: '模型实验室' } },
      { path: 'announcements', name: 'AdminAnnouncements', component: AdminAnnouncements, meta: { title: '公告管理' } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (auth.token && !auth.user) {
    await auth.initAuth()
  }

  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { name: 'login' }
  }

  // RBAC 动态权限守卫：仅管理员可访问 /admin
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { name: 'workspace' }
  }

  // 共享登录页分流：登录后按角色进入管理端或用户端
  if (['login', 'register', 'forgot'].includes(String(to.name)) && auth.isLoggedIn) {
    return auth.isAdmin ? { path: '/admin/dashboard' } : { name: 'workspace' }
  }

  return true
})

export default router
