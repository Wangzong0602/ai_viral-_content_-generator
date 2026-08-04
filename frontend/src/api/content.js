// 内容创作相关 API
// 注意：SSE 流式接口不能用 axios（它无法处理流式响应），
// 生成流程用浏览器原生 EventSource 实现（见 Workspace.vue）
import request from '../utils/request'

// 生成选题：输入关键词 + 平台，返回 5 个选题（templateId 可选，contentType 内容形态 P3 扩展）
// 注意：事实敏感题材（获奖/人名/新闻等）会先联网搜索再生成选题，耗时可达 20-40 秒，
// 必须单独设置长超时（默认 axios 30 秒不够）
export function generateTopics(keyword, platform, templateId = null, contentType = 'article') {
  return request.post(
    '/api/v1/content/topics',
    { keyword, platform, template_id: templateId, content_type: contentType },
    { timeout: 120000 } // 120 秒：给足联网搜索 + 生成时间
  )
}

// 历史记录列表（支持筛选：platform 平台 / keyword 搜索 / favorite 只看收藏）
export function getTasks({ limit = 50, platform = '', keyword = '', favorite = false } = {}) {
  const params = { limit }
  if (platform) params.platform = platform
  if (keyword) params.keyword = keyword
  if (favorite) params.favorite = true
  return request.get('/api/v1/content/tasks', { params })
}

// 历史记录详情
export function getTaskDetail(id) {
  return request.get(`/api/v1/content/tasks/${id}`)
}

// AI 配图：根据文章内容生成配图
// 返回 { images: [{ url, scene }] }
// operation: generate=常规生成 regenerate=重新生成单张（需要 scene）
// taskId: 关联的创作任务 ID（配图记录落库，历史记录可查）
// 注意：配图生成较慢（30-60 秒），必须单独设长超时（默认 axios 30 秒不够）
export function generateImages(content, count = 3, style = '插画卡通', operation = 'generate', scene = '', taskId = null) {
  return request.post(
    '/api/v1/content/images/generate',
    { content, count, style, operation, scene, task_id: taskId },
    { timeout: 180000 } // 180 秒：给足生成 + 重试时间
  )
}

// 多平台适配：一篇文章改写成多个平台版本
// 返回 { results: [{ platform, content, success, error }] }
// 注意：多个平台并发改写（20-40 秒），需要长超时
export function adaptContent(content, platforms) {
  return request.post(
    '/api/v1/content/adapt',
    { content, platforms },
    { timeout: 180000 }
  )
}

// 删除历史记录（软删除）
export function deleteTask(id) {
  return request.delete(`/api/v1/content/tasks/${id}`)
}

// 收藏/取消收藏
export function toggleFavorite(id, favorite) {
  return request.put(`/api/v1/content/tasks/${id}/favorite`, null, {
    params: { favorite },
  })
}

// 爆文逆向分析：输入链接或内容，返回拆解报告
// 返回 { title, content_len, report: { title_hook, opening_3s, ... } }
export function analyzeArticle(inputText) {
  return request.post(
    '/api/v1/content/analyze',
    { input_text: inputText },
    { timeout: 120000 } // 分析需 10-30 秒，长超时
  )
}

// 批量内容生成
// 创建批量任务：keywords_text 支持每行一个或逗号/分号分隔
export function createBatch(name, platform, keywordsText) {
  return request.post('/api/v1/content/batch', {
    name,
    platform,
    keywords_text: keywordsText,
  })
}

// 批量任务列表
export function getBatches(limit = 20) {
  return request.get('/api/v1/content/batch', { params: { limit } })
}

// 批量任务详情（含每篇状态，轮询进度用）
export function getBatchDetail(id) {
  return request.get(`/api/v1/content/batch/${id}`)
}

// 数据看板总览统计
// 返回 { summary, trend, platforms, quality_dist }
export function getDashboardOverview(days = 30) {
  return request.get('/api/v1/dashboard/overview', { params: { days } })
}

// 内容模板列表（可按平台过滤）
export function getTemplates(platform = '') {
  return request.get('/api/v1/content/templates', { params: { platform } })
}

// ============ 后台管理（仅管理员） ============
export function getAdminStats() {
  return request.get('/api/v1/admin/stats')
}

export function getAdminUsers(keyword = '') {
  return request.get('/api/v1/admin/users', { params: { keyword } })
}

export function updateUserStatus(id, status) {
  return request.put(`/api/v1/admin/users/${id}/status`, { status })
}

export function updateUserAdmin(id, isAdmin) {
  return request.put(`/api/v1/admin/users/${id}/admin`, null, { params: { is_admin: isAdmin } })
}

export function getAdminContents(keyword = '', platform = '') {
  return request.get('/api/v1/admin/contents', { params: { keyword, platform } })
}

export function deleteAdminContent(id) {
  return request.delete(`/api/v1/admin/contents/${id}`)
}

// 套餐管理（管理端）：列表 / 新增 / 编辑 / 下架
export function getAdminPlans() {
  return request.get('/api/v1/admin/plans')
}

export function createAdminPlan(data) {
  return request.post('/api/v1/admin/plans', data)
}

export function updateAdminPlan(id, data) {
  return request.put(`/api/v1/admin/plans/${id}`, data)
}

export function deleteAdminPlan(id) {
  return request.delete(`/api/v1/admin/plans/${id}`)
}

// 订单管理（管理端）：列表（可按状态/关键词筛选）
export function getAdminOrders({ status = '', keyword = '', limit = 50 } = {}) {
  const params = { limit }
  if (status) params.order_status = status
  if (keyword) params.keyword = keyword
  return request.get('/api/v1/admin/orders', { params })
}

// 手动开通/续期用户会员（管理端）
export function grantMembership(userId, planId, days = null) {
  const body = { plan_id: planId, note: '管理员手动开通' }
  if (days) body.days = days
  return request.put(`/api/v1/admin/users/${userId}/membership`, body)
}
