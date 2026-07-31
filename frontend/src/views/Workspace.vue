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

        <!-- 选题展示（两步合一：自动选中第一个，同时让用户能看到） -->
        <div v-if="topics.length" class="topics-section">
          <div class="topics-title">
            <el-tag type="success" effect="plain">AI 已生成 {{ topics.length }} 个爆款选题，自动采用第 1 个继续创作</el-tag>
          </div>
          <div class="topic-list">
            <div
              v-for="(t, i) in topics"
              :key="i"
              class="topic-item"
              :class="{ 'topic-active': i === 0 }"
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

        <!-- 在线编辑（textarea 双向绑定） -->
        <el-input
          v-model="finalContent"
          type="textarea"
          :rows="20"
          resize="vertical"
          class="result-editor"
        />
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
import { generateTopics } from '../api/content'

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

// 生成状态
const generating = ref(false) // 是否正在生成
const streaming = ref(false) // 是否正在流式输出正文
const streamText = ref('') // 流式正文（打字机）
const es = ref(null) // EventSource 实例（用于中途断开）

// 结果
const finalContent = ref('')
const qualityReport = ref(null)
const qualityScore = ref(0)

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
    // 延迟到页面渲染完成后自动触发生成
    setTimeout(() => startGenerate(), 300)
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

// ---------- 选择选题（两步合一：默认选第一个） ----------
function selectTopic(index) {
  selectedTopic.value = topics.value[index]
  topics.value.forEach((t, i) => {})
}

// ---------- 开始生成 ----------
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
    // 两步合一：自动采用第一个选题，立即进入完整创作
    selectedTopic.value = topics.value[0]
    phase.value = 'topics'
    startStreamGeneration()
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

function exportMarkdown() {
  const md = `# ${selectedTopic.value?.title || 'AI 生成文章'}\n\n${finalContent.value}\n`
  downloadFile(md, `爆文-${selectedTopic.value?.title?.slice(0, 20) || '未命名'}.md`)
  ElMessage.success('已导出 Markdown 文件')
}

function exportTxt() {
  downloadFile(finalContent.value, `爆文-${selectedTopic.value?.title?.slice(0, 20) || '未命名'}.txt`, 'text/plain')
  ElMessage.success('已导出纯文本文件')
}

// ---------- 重新创作 ----------
function resetAll() {
  // 断开可能残留的连接，重置所有状态
  if (es.value) es.value.close()
  keyword.value = ''
  topics.value = []
  streamText.value = ''
  finalContent.value = ''
  qualityReport.value = null
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

.result-editor :deep(.el-textarea__inner) {
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  line-height: 1.8;
}
</style>
