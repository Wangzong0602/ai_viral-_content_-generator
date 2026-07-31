// 用户状态管理（Pinia）
// 职责：保存登录态（token + 用户信息），提供登录/注册/登出操作
// localStorage 持久化：刷新页面后依然保持登录状态
import { defineStore } from 'pinia'
import { loginApi, registerApi, logoutApi } from '../api/auth'

export const useUserStore = defineStore('user', {
  // ---------- 状态 ----------
  state: () => ({
    token: localStorage.getItem('token') || '', // 从本地存储恢复登录态
    user: JSON.parse(localStorage.getItem('user') || 'null'), // 用户信息
  }),

  // ---------- 计算属性 ----------
  getters: {
    isLoggedIn: (state) => !!state.token,
    nickname: (state) => state.user?.nickname || '未登录',
  },

  // ---------- 操作 ----------
  actions: {
    // 保存登录结果（token + 用户信息）到内存和本地存储
    _saveAuth(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify(user))
    },

    // 登录：调用后端接口，成功后保存状态
    async login(account, password) {
      const data = await loginApi(account, password)
      this._saveAuth(data.access_token, data.user)
      return data
    },

    // 注册：成功后自动登录（后端注册接口直接返回 token）
    async register(phone, password, nickname) {
      const data = await registerApi(phone, password, nickname)
      this._saveAuth(data.access_token, data.user)
      return data
    },

    // 登出：调后端销毁会话 + 清空本地状态
    async logout() {
      try {
        await logoutApi()
      } finally {
        this.token = ''
        this.user = null
        localStorage.removeItem('token')
        localStorage.removeItem('user')
      }
    },
  },
})
