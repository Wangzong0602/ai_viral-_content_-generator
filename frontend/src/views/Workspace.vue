<template>
  <!-- 创作工作台（核心页面） -->
  <div class="workspace">
    <!-- 顶部导航栏 -->
    <header class="header">
      <div class="header-left">
        <span class="logo">✍️ AI 爆文智能创作平台</span>
        <el-menu mode="horizontal" :default-active="route.path" router :ellipsis="false" class="nav-menu">
          <el-menu-item index="/">创作工作台</el-menu-item>
          <el-menu-item index="/history">历史记录</el-menu-item>
        </el-menu>
      </div>
      <div class="header-right">
        <el-dropdown @command="handleUserCommand">
          <span class="user-info">
            <el-avatar :size="30" :src="userStore.user?.avatar || ''">{{ avatarText }}</el-avatar>
            {{ userStore.nickname }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <!-- 主体内容 -->
    <main class="main">
      <!-- ========== 第一步：输入创作需求 ========== -->
      <el-card class="input-card" v-show="phase === 'input' || phase === 'topics'">
        <div class="input-row">
          <el-input
            v-model="keyword"
            placeholder="输入创作主题或关键词，如：AI工具提升效率、职场成长、健康养生..."
            size="large"
            clearable
            :disabled="generating"
            @keyup.enter="startGenerate"
          />
          <el-select v-model="platform" size="large" style="width: 150px" :disabled="generating">
            <el-option v-for="p in platforms" :key="p" :label="p" :value="p" />
          </el-select>
          <el-button type="primary" size="large" :loading="loadingTopics" :disabled="generating" @click="startGenerate">
            一键生成爆文
          </el-button>
        </div>

        <!-- 选题展示（两步分离：生成后停留，用户自己选择再开始创作） -->
        <div v-if="topics.length" class="topics-section">
          <div class="topics-title">
            <el-tag type="success" effect="plain">
              AI 已生成 {{ topics.length }} 个爆款选题，请点击选择一个（当前：{{ selectedIndex + 1 }}）
            </el-tag>
          </div>
          <div class="topic-list">
            <div
              v-for="(t, i) in topics"
              :key="i"
              class="topic-item"
              :class="{ 'topic-active': selectedIndex === i }"
              @click="selectTopic(i)"
            >
              <span class="topic-index">{{ i + 1 }}</span>
              <div class="topic-body">
                <div class="topic-title">{{ t.title }}</div>
                <div class="topic-meta">
                  <span v-if="t.target_audience">🎯 {{ t.target_audience }}</span>
                  <span v-if="t.expected_effect">📈 {{ t.expected_effect }}</span>
                </div>
              </div>
            </div>
          </div>
          <!-- 开始创作按钮：用户确认选题后触发 -->
          <div class="topics-action">
            <el-button type="primary" size="large" :loading="generating" @click="startStreamGeneration">
              🚀 用「{{ selectedTopic?.title || '第1个' }}」开始创作
            </el-button>
            <el-button size="large" :disabled="generating" @click="resetAll">🔄 换个主题</el-button>
          </div>
        </div>
      </el-card>

      <!-- ========== 第二步：流式生成过程 ========== -->
      <el-card v-show="generating" class="gen-card">
        <template #header>
          <div class="gen-header">
            <span>生成进度</span>
            <el-tag :type="progressTagType" size="small">{{ currentStepName }}</el-tag>
          </div>
        </template>

        <!-- 步骤进度条 -->
        <div class="steps">
          <div v-for="(step, i) in steps" :key="step.name" class="step-item" :class="stepState(i)">
            <span class="step-icon">{{ stepState(i) === 'done' ? '✅' : stepState(i) === 'active' ? '⏳' : '⚪' }}</span>
            <span class="step-name">{{ step.label }}</span>
          </div>
        </div>

        <!-- 流式正文（打字机效果） -->
        <div class="stream-box">
          <div v-if="!streamText" class="stream-placeholder">AI 正在思考选题和创作策略，请稍候...</div>
          <div v-else class="stream-content">{{ streamText }}</div>
          <div v-if="streaming" class="stream-cursor">▍</div>
        </div>
      </el-card>

      <!-- ========== 第三步：结果展示与操作 ========== -->
      <el-card v-show="phase === 'result'" class="result-card">
        <template #header>
          <div class="result-header">
            <span>创作完成</span>
            <div class="result-actions">
              <el-button size="small" @click="copyContent">📋 一键复制</el-button>
              <el-button size="small" type="primary" @click="exportMarkdown">⬇️ 导出 Markdown</el-button>
              <el-button size="small" @click="exportHtml">🌐 导出 HTML（含图）</el-button>
              <el-button size="small" @click="exportTxt">⬇️ 导出纯文本</el-button>
              <el-button size="small" type="success" @click="resetAll">🔄 再写一篇</el-button>
            </div>
          </div>
        </template>

        <!-- 质量报告 -->
        <div v-if="qualityReport" class="quality-report">
          <el-tag :type="qualityReport.has_sensitive ? 'danger' : 'success'" size="small">
            {{ qualityReport.has_sensitive ? `⚠️ 含敏感词：${qualityReport.words.join('、')}` : '✅ 内容安全，无敏感词' }}
          </el-tag>
          <el-tag type="info" size="small">质量分：{{ qualityScore }}</el-tag>
        </div>

        <!-- AI 配图区 -->
        <div class="image-section">
          <div class="image-toolbar">
            <span class="image-title">🖼️ AI 配图</span>
            <el-select v-model="imageStyle" size="small" style="width: 120px" :disabled="imageLoading">
              <el-option v-for="s in imageStyles" :key="s" :label="s" :value="s" />
            </el-select>
            <el-button
              size="small"
              type="primary"
              :loading="imageLoading"
              :disabled="!finalContent"
              @click="handleGenerateImages"
            >
              {{ images.length ? '🔄 重新配图' : '✨ 生成配图' }}
            </el-button>
          </div>

          <!-- 图片网格 -->
          <div v-if="images.length" class="image-grid">
            <div v-for="(img, i) in images" :key="i" class="image-item">
              <el-image
                :src="img.url"
                fit="cover"
                :preview-src-list="images.map((x) => x.url)"
                preview-teleported
                class="image-preview"
              />
              <div class="image-actions">
                <el-button size="small" :loading="img.regenerating" @click="regenerateImage(img, i)">
                  🔄 换一张
                </el-button>
              </div>
            </div>
          </div>

          <!-- 加载占位 -->
          <div v-if="imageLoading" class="image-loading">
            <el-skeleton :rows="1" animated class="skeleton" />
            <div class="loading-text">AI 正在根据文章内容构思配图，约需 20-60 秒...</div>
          </div>
        </div>

        <!-- 🌐 多平台适配区 -->
        <div class="image-section">
          <div class="image-toolbar">
            <span class="image-title">🌐 多平台适配</span>
            <el-select
              v-model="adaptPlatforms"
              multiple
              size="small"
              style="width: 280px"
              placeholder="选择目标平台（可多选）"
              :disabled="adaptLoading"
            >
              <el-option v-for="p in adaptPlatformOptions" :key="p" :label="p" :value="p" />
            </el-select>
            <el-button
              size="small"
              type="primary"
              :loading="adaptLoading"
              :disabled="!finalContent || !adaptPlatforms.length"
              @click="handleAdapt"
            >
              🚀 生成多平台版本
            </el-button>
          </div>

          <!-- 适配结果：每个平台一个折叠面板 -->
          <div v-if="adaptResults.length" class="adapt-results">
            <el-collapse>
              <el-collapse-item
                v-for="(item, i) in adaptResults"
                :key="item.platform"
                :title="`${item.success ? '✅' : '❌'} ${item.platform} 版本（${item.content.length} 字）${item.warning ? ' ⚠️' : ''}`"
                :name="i"
              >
                <div v-if="item.success">
                  <el-alert
                    v-if="item.warning"
                    :title="item.warning"
                    type="warning"
                    :closable="false"
                    show-icon
                    class="adapt-warning"
                  />
                  <el-input
                    :model-value="item.content"
                    type="textarea"
                    :rows="12"
                    resize="vertical"
                    readonly
                  />
                  <div class="adapt-actions">
                    <el-button size="small" @click="copyAdapt(item)">📋 复制</el-button>
                    <el-button size="small" type="primary" @click="exportAdapt(item)">⬇️ 导出 MD</el-button>
                  </div>
                </div>
                <el-alert v-else type="error" :title="`${item.platform} 适配失败`" :description="item.error" show-icon />
              </el-collapse-item>
            </el-collapse>
          </div>

          <!-- 加载占位 -->
          <div v-if="adaptLoading" class="image-loading">
            <el-skeleton :rows="1" animated class="skeleton" />
            <div class="loading-text">AI 正在为各平台改写版本（并发生成），约需 20-40 秒...</div>
          </div>
        </div>

        <!-- 在线编辑（textarea 双向绑定） -->
        <el-input
          v-model="finalContent"
          type="textarea"
          :rows="20"
          resize="vertical"
          class="result-editor"
        />
      </el-card>

      <!-- ========== 爆文逆向分析（学习功能，独立于创作流程） ========== -->
      <el-card class="analyze-card">
        <template #header>
          <div class="gen-header">
            <span>🔍 爆文逆向分析</span>
            <el-tag size="small" type="info">学习功能：拆解一篇爆文为什么能火</el-tag>
          </div>
        </template>

        <!-- 输入区 -->
        <div class="analyze-input">
          <el-input
            v-model="analyzeInput"
            type="textarea"
            :rows="5"
            resize="vertical"
            placeholder="粘贴爆文链接（自动抓取）或直接粘贴文章全文，例如：https://... 或 整篇文章内容..."
          />
          <div class="analyze-toolbar">
            <el-button
              type="primary"
              :loading="analyzeLoading"
              :disabled="!analyzeInput.trim()"
              @click="handleAnalyze"
            >
              🔍 开始分析
            </el-button>
            <span v-if="analyzeInput.startsWith('http')" class="analyze-hint">已检测到链接，将自动抓取正文</span>
          </div>
        </div>

        <!-- 分析结果 -->
        <div v-if="analyzeResult" class="analyze-result">
          <div v-if="analyzeResult.title" class="analyze-title">{{ analyzeResult.title }}</div>
          <div class="analyze-meta">正文 {{ analyzeResult.content_len }} 字</div>
          <el-divider />
          <div class="analyze-report">
            <div v-for="item in analyzeReportItems" :key="item.key" class="report-item">
              <div class="report-label">{{ item.label }}</div>
              <div class="report-text">{{ analyzeResult.report[item.key] }}</div>
            </div>
          </div>
        </div>

        <!-- 加载占位 -->
        <div v-if="analyzeLoading" class="image-loading">
          <el-skeleton :rows="2" animated class="skeleton" />
          <div class="loading-text">AI 正在拆解爆文要素，约需 10-30 秒...</div>
        </div>
      </el-card>
    </main>
  </div>
</template>

<script setup>
// 创作工作台核心逻辑
// 流程（两步合一）：
// 1. 输入主题 + 平台 → POST /content/topics 生成 5 个选题
// 2. 自动选第 1 个 → EventSource 连接 /content/generate（SSE 流式）
// 3. 实时渲染：进度事件（步骤条）+ content 事件（打字机）
// 4. 完成后展示结果：复制 / 导出 Markdown / 导出纯文本
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import { generateTopics, generateImages, adaptContent, analyzeArticle } from '../api/content'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// ---------- 状态 ----------
const platforms = ['小红书', '公众号', '知乎']
const keyword = ref('')
const platform = ref('小红书')

// 阶段：input=输入  topics=选题  generating=生成中  result=结果
const phase = ref('input')
const loadingTopics = ref(false)

// 选题
const topics = ref([])
const selectedTopic = ref(null)
const selectedIndex = ref(0) // 当前选中的选题序号（默认第 1 个）

// 生成状态
const generating = ref(false) // 是否正在生成
const streaming = ref(false) // 是否正在流式输出正文
const streamText = ref('') // 流式正文（打字机）
const es = ref(null) // EventSource 实例（用于中途断开）
const currentTaskId = ref(null) // 当前创作任务的 ID（配图时关联落库）

// 结果
const finalContent = ref('')
const qualityReport = ref(null)
const qualityScore = ref(0)

// AI 配图状态
const images = ref([]) // 配图列表 [{ url, scene, regenerating }]
const imageLoading = ref(false) // 是否正在配图
const imageStyle = ref('插画卡通') // 配图风格
const imageStyles = ['插画卡通', '写实摄影', '科技未来', '简约扁平', '国潮古风']

// 多平台适配状态
const adaptPlatforms = ref([]) // 选中的目标平台
const adaptPlatformOptions = ['小红书', '公众号', '知乎']
const adaptResults = ref([]) // 适配结果 [{ platform, content, success, error }]
const adaptLoading = ref(false) // 是否正在适配

// 爆文逆向分析状态
const analyzeInput = ref('') // 输入的链接或内容
const analyzeLoading = ref(false) // 是否正在分析
const analyzeResult = ref(null) // 分析结果 { title, content_len, report }
// 报告展示字段（顺序固定）
const analyzeReportItems = [
  { key: 'title_hook', label: '🎯 标题钩子' },
  { key: 'opening_3s', label: '⏱️ 开头 3 秒' },
  { key: 'content_structure', label: '📐 内容结构' },
  { key: 'emotion_points', label: '💗 情绪价值' },
  { key: 'cta', label: '📣 行动召唤' },
  { key: 'seo_keywords', label: '🔎 SEO 关键词' },
  { key: 'overall', label: '📝 总体方法论' },
]

// 步骤定义（与后端节点一一对应）
const steps = [
  { name: 'resolve_topic', label: '选题解析' },
  { name: 'logic_analyzer', label: '爆文逻辑分析' },
  { name: 'content_writer', label: '文案创作' },
  { name: 'polish_agent', label: '润色优化' },
  { name: 'layout_agent', label: '排版整合' },
  { name: 'quality_checker', label: '质量审核' },
]
const currentStep = ref('') // 当前执行到的步骤名

// 当前步骤中文名（进度标签显示）
const currentStepName = computed(() => {
  if (!currentStep.value) return '准备中'
  return steps.find((s) => s.name === currentStep.value)?.label || currentStep.value
})

// 进度标签颜色：quality=绿（完成） error=红（失败）
const progressTagType = computed(() =>
  phase.value === 'result' ? 'success' : 'warning'
)

// 头像文字（昵称首字符）
const avatarText = computed(() => (userStore.nickname || '用').charAt(0))

// 从历史记录"复用"跳转过来时：预填关键词并自动开始生成
// URL 格式：/?keyword=xxx&platform=小红书&auto=1
if (route.query.keyword) {
  keyword.value = String(route.query.keyword)
  if (route.query.platform && platforms.includes(String(route.query.platform))) {
    platform.value = String(route.query.platform)
  }
  if (route.query.auto === '1') {
    // 历史记录复用场景：延迟到页面渲染完成后，生成选题后自动开始创作
    setTimeout(() => {
      startGenerate().then(() => {
        // 选题生成后（已有默认选中第 1 个），自动开始创作
        startStreamGeneration()
      })
    }, 300)
  }
}

// ---------- 步骤条状态 ----------
function stepState(index) {
  const step = steps[index]
  if (phase.value === 'result') return 'done' // 全部完成
  if (currentStep.value === step.name) return 'active' // 当前执行中
  // 已执行过的步骤（步骤列表中排位更早）
  const curIndex = steps.findIndex((s) => s.name === currentStep.value)
  if (curIndex === -1) return 'wait'
  return index < curIndex ? 'done' : 'wait'
}

// ---------- 选择选题（两步分离：用户点击自己的想要的选题） ----------
function selectTopic(index) {
  selectedIndex.value = index
  selectedTopic.value = topics.value[index]
}

// ---------- 第一步：生成选题（只生成，不自动创作） ----------
async function startGenerate() {
  if (!keyword.value.trim()) {
    ElMessage.warning('请输入创作主题或关键词')
    return
  }
  loadingTopics.value = true
  try {
    // 第一步：生成选题
    const data = await generateTopics(keyword.value.trim(), platform.value)
    topics.value = data.topics || []
    if (!topics.value.length) {
      ElMessage.error('选题生成失败，请重试')
      return
    }
    // 默认选中第 1 个，但【不】自动创作——等用户自己选择
    selectedIndex.value = 0
    selectedTopic.value = topics.value[0]
    phase.value = 'topics'
  } catch (e) {
    // 错误已由 axios 拦截器统一提示
  } finally {
    loadingTopics.value = false
  }
}

// ---------- SSE 流式创作 ----------
function startStreamGeneration() {
  // 重置状态
  generating.value = true
  streaming.value = false
  streamText.value = ''
  finalContent.value = ''
  qualityReport.value = null
  currentStep.value = ''

  // 构造 SSE URL：EventSource 无法带 Authorization 头，token 放 URL 参数
  const token = localStorage.getItem('token')
  const params = new URLSearchParams({
    keyword: keyword.value.trim(),
    platform: platform.value,
    selected_title: selectedTopic.value.title,
    token: token,
  })

  // 创建 EventSource 连接
  es.value = new EventSource(`/api/v1/content/generate?${params}`)

  // 监听 progress 事件（步骤进度）
  es.value.addEventListener('progress', (e) => {
    const data = JSON.parse(e.data)
    currentStep.value = data.step
  })

  // 监听 content 事件（流式正文增量 → 打字机）
  es.value.addEventListener('content', (e) => {
    const chunk = JSON.parse(e.data)
    streaming.value = true
    streamText.value += chunk
  })

  // 监听 complete 事件（生成完成）
  es.value.addEventListener('complete', (e) => {
    const data = JSON.parse(e.data)
    finalContent.value = data.content
    qualityReport.value = data.sensitive_report
    qualityScore.value = data.quality_score
    currentTaskId.value = data.task_id // 保存任务 ID（配图落库关联用）
    generating.value = false
    streaming.value = false
    phase.value = 'result'
    es.value.close()
    ElMessage.success('创作完成！')
  })

  // 监听 error 事件（后端生成失败）
  es.value.addEventListener('error', (e) => {
    // 注意：EventSource 的 error 事件有两种：
    // 1. 服务器主动发 event:error → 有 data 可解析
    // 2. 连接断开/网络错误 → 无 data
    if (e.data) {
      try {
        const data = JSON.parse(e.data)
        ElMessage.error(data.detail || '生成失败')
      } catch {
        ElMessage.error('生成失败')
      }
    } else {
      ElMessage.error('连接中断，请重试')
    }
    generating.value = false
    streaming.value = false
    es.value.close()
  })
}

// ---------- 复制内容 ----------
async function copyContent() {
  try {
    await navigator.clipboard.writeText(finalContent.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    // 浏览器安全策略可能拒绝（非 https），降级方案
    const textarea = document.createElement('textarea')
    textarea.value = finalContent.value
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    ElMessage.success('已复制到剪贴板')
  }
}

// ---------- 导出文件 ----------
function downloadFile(content, filename, type = 'text/markdown') {
  // 创建 Blob（二进制大对象）并触发浏览器下载
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url) // 释放内存
}

// 生成 Markdown 图片引用块（图在文章末尾集中展示）
function buildMarkdownImages() {
  if (!images.value.length) return ''
  const lines = ['', '---', '', '## 📷 配图', '']
  images.value.forEach((img, i) => {
    // 转成后端绝对 URL（方便本地查看时也能加载，服务运行期间有效）
    const absUrl = `http://127.0.0.1:8001${img.url}`
    lines.push(`![配图${i + 1}](${absUrl})`)
  })
  lines.push('')
  return lines.join('\n')
}

function exportMarkdown() {
  const title = selectedTopic.value?.title || 'AI 生成文章'
  // Markdown 导出：标题 + 正文 + 配图引用（MD 本身不支持内嵌二进制，用 URL 引用）
  const md = `# ${title}\n\n${finalContent.value}\n${buildMarkdownImages()}`
  downloadFile(md, `爆文-${title?.slice(0, 20) || '未命名'}.md`)
  ElMessage.success('已导出 Markdown 文件（含配图引用）')
}

// 导出 HTML：图片转 base64 内嵌进文件，任何电脑打开都能看到（不依赖后端）
async function exportHtml() {
  const title = selectedTopic.value?.title || 'AI 生成文章'
  let imgHtml = ''
  // 把每张图转成 base64 内嵌（fetch 图片 → base64）
  for (let i = 0; i < images.value.length; i++) {
    const url = images.value[i].url
    try {
      const resp = await fetch(url)
      const blob = await resp.blob()
      const base64 = await new Promise((resolve) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result)
        reader.readAsDataURL(blob)
      })
      imgHtml += `<div style="margin:16px 0;text-align:center;"><img src="${base64}" alt="配图${i + 1}" style="max-width:100%;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);" /></div>\n`
    } catch {
      imgHtml += `<p style="color:#999;">配图${i + 1}加载失败（后端未运行）</p>\n`
    }
  }
  // 转义正文中的 HTML 特殊字符，防止正文内容破坏页面结构
  const escapeHtml = (s) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br/>')
  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<title>${escapeHtml(title)}</title>
<style>
body { max-width: 800px; margin: 40px auto; padding: 0 20px; font-family: 'PingFang SC','Microsoft YaHei',sans-serif; line-height: 1.8; color: #333; }
h1 { border-bottom: 2px solid #409eff; padding-bottom: 10px; }
</style>
</head>
<body>
<h1>${escapeHtml(title)}</h1>
<div>${escapeHtml(finalContent.value)}</div>
${imgHtml}
</body>
</html>`
  downloadFile(html, `爆文-${title?.slice(0, 20) || '未命名'}.html`, 'text/html')
  ElMessage.success('已导出 HTML（图片已内嵌，可随处打开）')
}

function exportTxt() {
  downloadFile(finalContent.value, `爆文-${selectedTopic.value?.title?.slice(0, 20) || '未命名'}.txt`, 'text/plain')
  ElMessage.success('已导出纯文本文件')
}

// ---------- AI 配图 ----------
async function handleGenerateImages() {
  if (!finalContent.value) {
    ElMessage.warning('请先生成文章内容')
    return
  }
  imageLoading.value = true
  images.value = []
  try {
    const data = await generateImages(
      finalContent.value,
      3, // 默认生成 3 张
      imageStyle.value,
      'generate',
      '',
      currentTaskId.value // 关联创作任务（落库）
    )
    images.value = (data.images || []).map((img) => ({
      url: img.url,
      scene: img.scene || '',
      regenerating: false,
    }))
    ElMessage.success(`配图完成，共 ${images.value.length} 张`)
  } catch (e) {
    // 错误已由 axios 拦截器统一提示
  } finally {
    imageLoading.value = false
  }
}

// 单张重新生成（保持场景一致，换一张）
async function regenerateImage(img, index) {
  if (!img.scene) {
    ElMessage.warning('该图片缺少场景信息，无法重新生成')
    return
  }
  img.regenerating = true
  try {
    const data = await generateImages(
      finalContent.value,
      1,
      imageStyle.value,
      'regenerate',
      img.scene,
      currentTaskId.value // 关联创作任务（落库更新同场景记录）
    )
    if (data.images && data.images.length) {
      img.url = data.images[0].url
      ElMessage.success('已换一张')
    }
  } catch (e) {
    // 错误已由 axios 拦截器统一提示
  } finally {
    img.regenerating = false
  }
}

// ---------- 多平台适配 ----------
async function handleAdapt() {
  if (!finalContent.value) {
    ElMessage.warning('请先生成文章内容')
    return
  }
  if (!adaptPlatforms.value.length) {
    ElMessage.warning('请至少选择一个目标平台')
    return
  }
  adaptLoading.value = true
  adaptResults.value = []
  try {
    const data = await adaptContent(finalContent.value, [...adaptPlatforms.value])
    adaptResults.value = data.results || []
    const okCount = adaptResults.value.filter((r) => r.success).length
    ElMessage.success(`多平台适配完成：${okCount}/${adaptResults.value.length} 个平台成功`)
  } catch (e) {
    // 错误已由 axios 拦截器统一提示
  } finally {
    adaptLoading.value = false
  }
}

// 复制某个平台版本
async function copyAdapt(item) {
  try {
    await navigator.clipboard.writeText(item.content)
    ElMessage.success(`${item.platform} 版本已复制`)
  } catch {
    ElMessage.info('复制失败，请手动选择复制')
  }
}

// 导出某个平台版本为 MD
function exportAdapt(item) {
  const md = `# ${item.platform} 版本\n\n${item.content}\n`
  const blob = new Blob([md], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${item.platform}版本.md`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`${item.platform} 版本已导出`)
}

// ---------- 爆文逆向分析 ----------
async function handleAnalyze() {
  if (!analyzeInput.value.trim()) {
    ElMessage.warning('请输入文章链接或内容')
    return
  }
  analyzeLoading.value = true
  analyzeResult.value = null
  try {
    const data = await analyzeArticle(analyzeInput.value.trim())
    analyzeResult.value = data
    ElMessage.success('分析完成')
  } catch (e) {
    // 错误已由 axios 拦截器统一提示
  } finally {
    analyzeLoading.value = false
  }
}

// ---------- 重新创作 ----------
function resetAll() {
  // 断开可能残留的连接，重置所有状态
  if (es.value) es.value.close()
  keyword.value = ''
  topics.value = []
  selectedTopic.value = null
  selectedIndex.value = 0
  streamText.value = ''
  finalContent.value = ''
  qualityReport.value = null
  images.value = []
  adaptPlatforms.value = []
  adaptResults.value = []
  generating.value = false
  phase.value = 'input'
}

// ---------- 用户菜单 ----------
function handleUserCommand(command) {
  if (command === 'logout') {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}
</script>

<style scoped>
.workspace {
  min-height: 100vh;
}

/* 顶栏 */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 24px;
}

.logo {
  font-size: 18px;
  font-weight: 600;
  color: #409eff;
}

.nav-menu {
  border-bottom: none !important;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #606266;
}

/* 主体 */
.main {
  max-width: 1000px;
  margin: 24px auto;
  padding: 0 16px;
}

.input-card {
  margin-bottom: 16px;
}

.input-row {
  display: flex;
  gap: 12px;
}

/* 选题列表 */
.topics-section {
  margin-top: 20px;
}

.topics-title {
  margin-bottom: 12px;
}

.topic-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 选题下方的操作按钮区（开始创作 / 换个主题） */
.topics-action {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  align-items: center;
}

.topic-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.topic-item:hover {
  border-color: #409eff;
  background: #f5f9ff;
}

.topic-active {
  border-color: #67c23a;
  background: #f0f9eb;
}

.topic-index {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  font-size: 13px;
}

.topic-active .topic-index {
  background: #67c23a;
}

.topic-title {
  font-size: 15px;
  font-weight: 500;
  color: #303133;
}

.topic-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
  display: flex;
  gap: 16px;
}

/* 生成过程 */
.gen-card {
  margin-bottom: 16px;
}

.gen-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.steps {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border-radius: 16px;
  background: #f4f4f5;
  font-size: 12px;
  color: #909399;
}

.step-item.active {
  background: #ecf5ff;
  color: #409eff;
}

.step-item.done {
  background: #f0f9eb;
  color: #67c23a;
}

.stream-box {
  min-height: 200px;
  max-height: 400px;
  overflow-y: auto;
  padding: 16px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fafafa;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.8;
}

.stream-placeholder {
  color: #909399;
}

.stream-cursor {
  display: inline;
  color: #409eff;
  animation: blink 1s infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

/* 结果 */
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-actions {
  display: flex;
  gap: 8px;
}

.quality-report {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

/* AI 配图区 */
.image-section {
  margin-bottom: 16px;
  padding: 12px;
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  background: #fafafa;
}

.image-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.image-title {
  font-weight: 600;
  color: #303133;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.image-item {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #ebeef5;
  background: #fff;
}

.image-preview {
  width: 100%;
  height: 220px;
  display: block;
}

.image-actions {
  padding: 8px;
  display: flex;
  justify-content: center;
}

.image-loading {
  text-align: center;
  padding: 20px;
}

.loading-text {
  margin-top: 12px;
  color: #909399;
  font-size: 13px;
}

.skeleton {
  max-width: 400px;
  margin: 0 auto;
}

/* 多平台适配结果 */
.adapt-results {
  margin-top: 4px;
}

.adapt-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

.adapt-warning {
  margin-bottom: 12px;
}

/* 爆文逆向分析 */
.analyze-card {
  margin-top: 16px;
}

.analyze-input {
  margin-bottom: 8px;
}

.analyze-toolbar {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.analyze-hint {
  font-size: 12px;
  color: #67c23a;
}

.analyze-result {
  margin-top: 16px;
}

.analyze-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.analyze-meta {
  font-size: 12px;
  color: #909399;
}

.analyze-report {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.report-item {
  padding: 12px 16px;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}

.report-label {
  font-weight: 600;
  color: #409eff;
  margin-bottom: 6px;
}

.report-text {
  color: #606266;
  line-height: 1.7;
  white-space: pre-wrap;
}

.result-editor :deep(.el-textarea__inner) {
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  line-height: 1.8;
}
</style>
