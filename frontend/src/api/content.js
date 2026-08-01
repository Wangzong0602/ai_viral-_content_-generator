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

// AI 配图：根据文章内容生成配图
// 返回 { images: [{ url, scene }] }
// operation: generate=常规生成 regenerate=重新生成单张（需要 scene）
// 注意：配图生成较慢（30-60 秒），必须单独设长超时（默认 axios 30 秒不够）
export function generateImages(content, count = 3, style = '插画卡通', operation = 'generate', scene = '') {
  return request.post(
    '/api/v1/content/images/generate',
    { content, count, style, operation, scene },
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

// 爆文逆向分析：输入链接或内容，返回拆解报告
// 返回 { title, content_len, report: { title_hook, opening_3s, ... } }
export function analyzeArticle(inputText) {
  return request.post(
    '/api/v1/content/analyze',
    { input_text: inputText },
    { timeout: 120000 } // 分析需 10-30 秒，长超时
  )
}
