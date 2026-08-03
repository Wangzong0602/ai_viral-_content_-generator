// 会员中心相关 API
import request from '../utils/request'

// 套餐列表（免费版 + 上架付费套餐）
export function getPlansApi() {
  return request.get('/api/v1/membership/plans')
}

// 我的会员状态（当前套餐/到期时间/剩余天数）
export function getMyMembershipApi() {
  return request.get('/api/v1/membership/me')
}

// 创建订单（planId + 支付渠道 channel: virtual/wechat/alipay）
export function createOrderApi(planId, channel) {
  return request.post('/api/v1/membership/orders', { plan_id: planId, channel })
}

// 模拟支付（订单号）
export function payOrderApi(orderNo) {
  return request.post(`/api/v1/membership/orders/${orderNo}/pay`)
}

// 取消订单（订单号）
export function cancelOrderApi(orderNo) {
  return request.post(`/api/v1/membership/orders/${orderNo}/cancel`)
}

// 我的订单列表
export function getMyOrdersApi() {
  return request.get('/api/v1/membership/orders')
}
