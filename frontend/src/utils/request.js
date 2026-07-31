// Axios 实例封装
// 统一处理：请求头注入 token、响应错误拦截（401 跳登录页等）
import axios from 'axios'
import { ElMessage } from 'element-plus'

// 创建 axios 实例（baseURL 为空：走 vite 代理 /api → 后端 8001）
const request = axios.create({
  baseURL: '',
  timeout: 30000, // 30 秒超时
})

// ---------- 请求拦截器：每次请求自动带上 token ----------
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}` // 标准 Bearer 认证
  }
  return config
})

// ---------- 响应拦截器：统一错误处理 ----------
request.interceptors.response.use(
  (response) => response.data, // 成功：直接返回 data（去掉 axios 包装）
  (error) => {
    // 错误处理：HTTP 错误或网络错误统一提示
    const status = error.response?.status
    const detail = error.response?.data?.detail

    if (status === 401) {
      // 401：未认证/会话失效 → 清空登录态跳转登录页
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      ElMessage.error(detail || '登录已失效，请重新登录')
      // 延迟跳转，让用户看到提示
      setTimeout(() => (window.location.href = '/login'), 500)
    } else {
      // 其他错误（400/403/500...）：显示后端返回的 detail 信息
      ElMessage.error(detail || '请求失败，请稍后重试')
    }
    return Promise.reject(error)
  }
)

export default request
