// 认证相关 API（注册/登录/登出）
import request from '../utils/request'

// 注册：成功后自动登录（后端直接返回 token）
export function registerApi(phone, password, nickname) {
  return request.post('/api/v1/auth/register', { phone, password, nickname })
}

// 登录：手机号/邮箱 + 密码
export function loginApi(account, password) {
  return request.post('/api/v1/auth/login', { account, password })
}

// 登出：销毁后端 Redis 会话
export function logoutApi() {
  return request.post('/api/v1/auth/logout')
}
