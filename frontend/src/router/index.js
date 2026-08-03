// 路由配置：定义页面与 URL 的对应关系
// 所有需要登录的页面都用 meta.requiresAuth 标记，
// 在全局前置守卫里统一检查登录态（见下方 beforeEach）
import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'), // 懒加载：用到才加载
    meta: { title: '登录' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('../views/Register.vue'),
    meta: { title: '注册' },
  },
  {
    path: '/',
    name: 'workspace',
    component: () => import('../views/Workspace.vue'), // 创作工作台（核心页）
    meta: { title: '创作工作台', requiresAuth: true },
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('../views/History.vue'), // 历史记录页
    meta: { title: '历史记录', requiresAuth: true },
  },
  {
    path: '/batch',
    name: 'batch',
    component: () => import('../views/Batch.vue'), // 批量生成页
    meta: { title: '批量生成', requiresAuth: true },
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('../views/Dashboard.vue'), // 数据看板
    meta: { title: '数据看板', requiresAuth: true },
  },
  {
    path: '/membership',
    name: 'membership',
    component: () => import('../views/Membership.vue'), // 会员中心
    meta: { title: '会员中心', requiresAuth: true },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('../views/Admin.vue'), // 后台管理（仅管理员）
    meta: { title: '后台管理', requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(), // 使用 HTML5 历史模式（URL 无 # 号）
  routes,
})

// 全局前置守卫：每次路由跳转前执行
router.beforeEach((to) => {
  document.title = `${to.meta.title || ''} - AI 爆文智能创作平台`

  // 需要登录的页面：检查是否已登录，未登录跳转登录页
  if (to.meta.requiresAuth && !useUserStore().token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  // 已登录用户访问登录/注册页：直接回工作台
  if ((to.path === '/login' || to.path === '/register') && useUserStore().token) {
    return { path: '/' }
  }
})

export default router
