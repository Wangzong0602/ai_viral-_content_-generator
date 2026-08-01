<template>
  <!-- 历史记录页：查看/复用/删除历史生成 -->
  <div class="history-page">
    <!-- 顶部导航栏（与工作台一致） -->
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

    <main class="main">
      <el-card>
        <template #header>
          <div class="list-header">
            <span>历史记录（{{ tasks.length }} 条）</span>
            <el-button size="small" :loading="loading" @click="loadTasks">刷新</el-button>
          </div>
        </template>

        <!-- 空状态 -->
        <el-empty v-if="!loading && !tasks.length" description="暂无历史记录，去创作第一篇爆文吧！">
          <el-button type="primary" @click="router.push('/')">去创作</el-button>
        </el-empty>

        <!-- 记录列表 -->
        <el-table v-else :data="tasks" stripe @row-click="openDetail">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="selected_title" label="标题" min-width="200" show-overflow-tooltip />
          <el-table-column prop="platform" label="平台" width="90" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="quality_score" label="质量分" width="80" />
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button size="small" @click.stop="openDetail(row)">查看</el-button>
              <el-button size="small" type="primary" @click.stop="reuse(row)">复用</el-button>
              <el-button size="small" type="danger" @click.stop="deleteTask(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 详情对话框 -->
      <el-dialog v-model="detailVisible" title="记录详情" width="80%" top="5vh">
        <template v-if="currentTask">
          <div class="detail-meta">
            <el-tag size="small">{{ currentTask.platform }}</el-tag>
            <el-tag size="small" :type="statusType(currentTask.status)">{{ statusText(currentTask.status) }}</el-tag>
            <el-tag size="small" type="info">质量分 {{ currentTask.quality_score }}</el-tag>
            <el-tag v-if="currentTask.error_message" size="small" type="danger">失败原因：{{ currentTask.error_message }}</el-tag>
          </div>
          <div class="detail-title">{{ currentTask.selected_title }}</div>
          <div class="detail-content">{{ currentTask.content }}</div>
          <div class="detail-actions">
            <el-button size="small" @click="copyDetail">📋 复制</el-button>
            <el-button size="small" type="primary" @click="downloadDetail">⬇️ 导出 Markdown</el-button>
          </div>
        </template>
      </el-dialog>
    </main>
  </div>
</template>

<script setup>
// 历史记录页逻辑：加载列表 → 查看详情 → 复用（带参数跳工作台）→ 删除
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import { getTasks, getTaskDetail, deleteTask as deleteTaskApi } from '../api/content'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const tasks = ref([])
const loading = ref(false)

// 详情
const detailVisible = ref(false)
const currentTask = ref(null)

// 头像文字
const avatarText = computed(() => (userStore.nickname || '用').charAt(0))

// 状态映射
function statusText(status) {
  return { 0: '排队中', 1: '生成中', 2: '已完成', 3: '失败' }[status] || '未知'
}
function statusType(status) {
  return { 0: 'info', 1: 'warning', 2: 'success', 3: 'danger' }[status] || 'info'
}

// 时间格式化
function formatTime(t) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN', { hour12: false })
}

// 加载列表
async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await getTasks()
  } finally {
    loading.value = false
  }
}

// 打开详情（先查详情接口拿完整内容）
async function openDetail(row) {
  try {
    currentTask.value = await getTaskDetail(row.id)
    detailVisible.value = true
  } catch {
    // 错误已统一提示
  }
}

// 复用：带关键词跳转工作台（工作台通过 URL 参数预填）
function reuse(row) {
  // 把 keyword 和 platform 放进 URL 参数，工作台页面读取并自动生成
  router.push({
    path: '/',
    query: { keyword: row.keyword, platform: row.platform, auto: '1' },
  })
}

// 删除（软删除：后端将 status 改为 3，列表不再返回）
async function deleteTask(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.selected_title?.slice(0, 20)}」吗？`, '提示', {
      type: 'warning',
    })
    await deleteTaskApi(row.id)
    ElMessage.success('已删除')
    loadTasks() // 刷新列表
  } catch {
    // 用户取消 或 请求失败（错误已由 axios 拦截器统一提示）
  }
}

// 复制详情内容
async function copyDetail() {
  try {
    await navigator.clipboard.writeText(currentTask.value.content)
    ElMessage.success('已复制')
  } catch {
    ElMessage.info('复制失败，请手动选择复制')
  }
}

// 下载详情为 Markdown
function downloadDetail() {
  const md = `# ${currentTask.value.selected_title}\n\n${currentTask.value.content}\n`
  const blob = new Blob([md], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `爆文-${currentTask.value.selected_title?.slice(0, 20)}.md`
  a.click()
  URL.revokeObjectURL(url)
}

// 用户菜单
function handleUserCommand(command) {
  if (command === 'logout') {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}

onMounted(loadTasks)
</script>

<style scoped>
.history-page {
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

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.detail-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 12px;
}

.detail-content {
  white-space: pre-wrap;
  line-height: 1.8;
  max-height: 50vh;
  overflow-y: auto;
  padding: 16px;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}

.detail-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}
</style>
