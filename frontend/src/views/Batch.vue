<template>
  <!-- 批量生成页：一次提交多个关键词，后台逐篇生成 -->
  <div class="batch-page">
    <header class="header">
      <div class="header-left">
        <span class="logo">✍️ AI 爆文智能创作平台</span>
        <el-menu mode="horizontal" :default-active="route.path" router :ellipsis="false" class="nav-menu">
          <el-menu-item index="/">创作工作台</el-menu-item>
          <el-menu-item index="/batch">批量生成</el-menu-item>
          <el-menu-item index="/dashboard">数据看板</el-menu-item>`n          <el-menu-item index="/history">历史记录</el-menu-item>
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

    <main class="main">
      <!-- 创建批量任务 -->
      <el-card>
        <template #header>
          <div class="card-header">
            <span>📦 批量内容生成</span>
            <el-tag type="info" size="small">一次提交多个关键词，后台自动逐篇生成（每篇约 1-2 分钟）</el-tag>
          </div>
        </template>

        <div class="batch-form">
          <div class="form-row">
            <el-input v-model="batchName" placeholder="任务名称（可选）" style="width: 300px" maxlength="50" />
            <el-select v-model="batchPlatform" style="width: 150px">
              <el-option v-for="p in platforms" :key="p" :label="p" :value="p" />
            </el-select>
          </div>
          <el-input
            v-model="keywordsText"
            type="textarea"
            :rows="8"
            resize="vertical"
            placeholder="每行输入一个关键词，例如：&#10;职场效率提升&#10;时间管理技巧&#10;下班后的自我提升&#10;&#10;（也支持逗号/分号/顿号分隔）"
          />
          <div class="form-actions">
            <el-button type="primary" :loading="creating" :disabled="!keywordsText.trim()" @click="handleCreate">
              🚀 开始批量生成（{{ keywordCount }} 篇）
            </el-button>
            <span v-if="keywordCount > 30" class="form-hint">最多 30 篇，超出部分已忽略</span>
          </div>
        </div>
      </el-card>

      <!-- 批量任务列表 -->
      <el-card class="batch-list-card">
        <template #header>
          <div class="card-header">
            <span>批量任务列表</span>
            <el-button size="small" :loading="loading" @click="loadBatches">刷新</el-button>
          </div>
        </template>

        <el-empty v-if="!loading && !batches.length" description="暂无批量任务" />

        <el-table v-else :data="batches" stripe>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="任务名称" min-width="150" show-overflow-tooltip />
          <el-table-column prop="platform" label="平台" width="90" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="batchStatusType(row.status)" size="small">{{ batchStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="进度" width="160">
            <template #default="{ row }">
              <el-progress
                :percentage="Math.round(((row.success_count + row.fail_count) / row.total) * 100)"
                :status="row.status === 2 ? 'success' : row.status === 3 ? 'warning' : ''"
              />
            </template>
          </el-table-column>
          <el-table-column label="成功/失败" width="110">
            <template #default="{ row }">
              <span class="success-text">{{ row.success_count }}</span>
              <span class="fail-text"> / {{ row.fail_count }}</span>
              <span class="gray-text"> / {{ row.total }}</span>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button size="small" @click="openDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 批量任务详情对话框 -->
      <el-dialog v-model="detailVisible" title="批量任务详情" width="70%" top="5vh">
        <template v-if="currentBatch">
          <div class="detail-meta">
            <el-tag size="small">{{ currentBatch.platform }}</el-tag>
            <el-tag size="small" :type="batchStatusType(currentBatch.status)">
              {{ batchStatusText(currentBatch.status) }}
            </el-tag>
            <el-tag size="small" type="info">
              进度 {{ currentBatch.success_count + currentBatch.fail_count }}/{{ currentBatch.total }}
            </el-tag>
          </div>

          <!-- 每篇状态列表 -->
          <div class="items-list">
            <div v-for="item in currentBatch.items" :key="item.id" class="item-row">
              <el-tag :type="itemStatusType(item.status)" size="small">{{ itemStatusText(item.status) }}</el-tag>
              <span class="item-keyword">{{ item.keyword }}</span>
              <el-tooltip v-if="item.error_message" :content="item.error_message" placement="top">
                <el-icon class="item-error"><WarningFilled /></el-icon>
              </el-tooltip>
              <el-button v-if="item.task_id" size="small" type="primary" link @click="viewArticle(item)">
                查看正文
              </el-button>
            </div>
          </div>

          <!-- 自动刷新（生成中时） -->
          <div v-if="currentBatch.status === 0 || currentBatch.status === 1" class="auto-refresh">
            生成中，每 10 秒自动刷新进度...
          </div>
        </template>
      </el-dialog>
    </main>
  </div>
</template>

<script setup>
// 批量生成页逻辑：创建批量任务 → 轮询进度 → 查看每篇正文
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, WarningFilled } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import { createBatch, getBatches, getBatchDetail, getTaskDetail } from '../api/content'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const platforms = ['小红书', '公众号', '知乎']

// 创建表单
const batchName = ref('')
const batchPlatform = ref('小红书')
const keywordsText = ref('')
const creating = ref(false)

// 列表
const batches = ref([])
const loading = ref(false)

// 详情
const detailVisible = ref(false)
const currentBatch = ref(null)
let pollTimer = null // 轮询定时器

// 头像文字
const avatarText = computed(() => (userStore.nickname || '用').charAt(0))

// 关键词数量（预览用）
const keywordCount = computed(() => {
  if (!keywordsText.value.trim()) return 0
  return keywordsText.value.split(/[\n,，;；、]+/).filter((k) => k.trim()).length
})

// 状态映射
function batchStatusText(s) {
  return { 0: '排队中', 1: '生成中', 2: '已完成', 3: '部分失败' }[s] || '未知'
}
function batchStatusType(s) {
  return { 0: 'info', 1: 'warning', 2: 'success', 3: 'danger' }[s] || 'info'
}
function itemStatusText(s) {
  return { 0: '排队中', 1: '生成中', 2: '成功', 3: '失败' }[s] || '未知'
}
function itemStatusType(s) {
  return { 0: 'info', 1: 'warning', 2: 'success', 3: 'danger' }[s] || 'info'
}

function formatTime(t) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN', { hour12: false })
}

// ---------- 创建批量任务 ----------
async function handleCreate() {
  if (!keywordsText.value.trim()) {
    ElMessage.warning('请输入至少一个关键词')
    return
  }
  creating.value = true
  try {
    const batch = await createBatch(batchName.value, batchPlatform.value, keywordsText.value)
    ElMessage.success(`批量任务已创建（${batch.total} 篇），后台开始生成`)
    keywordsText.value = ''
    batchName.value = ''
    loadBatches()
    // 自动打开详情看进度
    openDetail(batch)
  } catch (e) {
    // 错误已由 axios 拦截器统一提示
  } finally {
    creating.value = false
  }
}

// ---------- 列表 ----------
async function loadBatches() {
  loading.value = true
  try {
    batches.value = await getBatches()
  } finally {
    loading.value = false
  }
}

// ---------- 详情（含自动轮询） ----------
async function openDetail(row) {
  detailVisible.value = true
  currentBatch.value = row
  await refreshDetail(row.id)
  // 生成中 → 启动自动轮询
  if (row.status === 0 || row.status === 1) {
    startPolling(row.id)
  }
}

async function refreshDetail(batchId) {
  try {
    const detail = await getBatchDetail(batchId)
    currentBatch.value = detail
    // 生成结束 → 停止轮询
    if (detail.status === 2 || detail.status === 3) {
      stopPolling()
      loadBatches()
    }
  } catch (e) {
    stopPolling()
  }
}

function startPolling(batchId) {
  stopPolling()
  pollTimer = setInterval(() => refreshDetail(batchId), 10000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// ---------- 查看某篇正文 ----------
async function viewArticle(item) {
  try {
    const task = await getTaskDetail(item.task_id)
    ElMessageBox.confirm(task.content.slice(0, 200) + '...', `正文预览：${item.keyword}`, {
      confirmButtonText: '去历史记录查看完整',
      cancelButtonText: '关闭',
      type: 'info',
    })
      .then(() => router.push('/history'))
      .catch(() => {})
  } catch (e) {
    // 错误已统一提示
  }
}

// ---------- 用户菜单 ----------
function handleUserCommand(command) {
  if (command === 'logout') {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}

onMounted(loadBatches)
</script>

<style scoped>
.batch-page {
  min-height: 100vh;
}

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

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #606266;
}

.main {
  max-width: 1100px;
  margin: 24px auto;
  padding: 0 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.batch-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-row {
  display: flex;
  gap: 12px;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.form-hint {
  font-size: 12px;
  color: #e6a23c;
}

.batch-list-card {
  margin-top: 16px;
}

.success-text {
  color: #67c23a;
}

.fail-text {
  color: #f56c6c;
}

.gray-text {
  color: #909399;
}

.detail-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.items-list {
  max-height: 50vh;
  overflow-y: auto;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 4px;
  border-bottom: 1px solid #f0f2f5;
}

.item-keyword {
  flex: 1;
  font-size: 14px;
  color: #303133;
}

.item-error {
  color: #f56c6c;
  cursor: pointer;
}

.auto-refresh {
  margin-top: 12px;
  font-size: 12px;
  color: #909399;
  text-align: center;
}
</style>
