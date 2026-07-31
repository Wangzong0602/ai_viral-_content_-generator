// 内容创作相关 API
// 注意：SSE 流式接口不能用 axios（它无法处理流式响应），
// 生成流程用浏览器原生 EventSource 实现（见 Workspace.vue）
import request from '../utils/request'

// 生成选题：输入关键词 + 平台，返回 5 个选题
export function generateTopics(keyword, platform) {
  return request.post('/api/v1/content/topics', { keyword, platform })
}

// 历史记录列表
export function getTasks(limit = 50) {
  return request.get('/api/v1/content/tasks', { params: { limit } })
}

// 历史记录详情
export function getTaskDetail(id) {
  return request.get(`/api/v1/content/tasks/${id}`)
}
