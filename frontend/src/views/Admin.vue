<template>
  <!-- 后台管理页（仅管理员）：左侧菜单 + 内容区（统计/用户/内容） -->
  <div class="admin-page">
    <header class="header">
      <div class="header-left">
        <span class="logo">✍️ AI 爆文智能创作平台</span>
        <el-menu mode="horizontal" :default-active="route.path" router :ellipsis="false" class="nav-menu">
          <el-menu-item index="/">创作工作台</el-menu-item>
          <el-menu-item index="/batch">批量生成</el-menu-item>
          <el-menu-item index="/dashboard">数据看板</el-menu-item>
          <el-menu-item index="/history">历史记录</el-menu-item>
          <el-menu-item index="/admin">后台管理</el-menu-item>
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

    <div class="admin-layout">
      <!-- 左侧菜单 -->
      <aside class="admin-sidebar">
        <div
          v-for="item in menus"
          :key="item.key"
          class="admin-menu-item"
          :class="{ active: activeMenu === item.key }"
          @click="switchMenu(item.key)"
        >
          {{ item.icon }} {{ item.label }}
        </div>
      </aside>

      <!-- 内容区 -->
      <main class="admin-content">
        <!-- ========== 数据总览 ========== -->
        <div v-if="activeMenu === 'stats'" class="panel">
          <h3 class="panel-title">📊 数据总览</h3>
          <div class="stats-grid">
            <el-card class="stat-card">
              <div class="stat-label">总用户数</div>
              <div class="stat-value">{{ stats.total_users }}</div>
              <div class="stat-sub">近 7 天新增 {{ stats.new_users_7d }}</div>
            </el-card>
            <el-card class="stat-card">
              <div class="stat-label">总生成记录</div>
              <div class="stat-value">{{ stats.total_contents }}</div>
              <div class="stat-sub">成功 {{ stats.success_contents }}</div>
            </el-card>
            <el-card class="stat-card">
              <div class="stat-label">总字数</div>
              <div class="stat-value">{{ formatChars(stats.total_chars) }}</div>
              <div class="stat-sub">累计输出</div>
            </el-card>
            <el-card class="stat-card">
              <div class="stat-label">活跃用户（7 天）</div>
              <div class="stat-value">{{ stats.active_users_7d }}</div>
              <div class="stat-sub">有创作行为的用户</div>
            </el-card>
          </div>
        </div>

        <!-- ========== 用户管理 ========== -->
        <div v-if="activeMenu === 'users'" class="panel">
          <div class="panel-header">
            <h3 class="panel-title">👥 用户管理</h3>
            <div class="panel-actions">
              <el-input
                v-model="userKeyword"
                placeholder="搜索手机号/昵称"
                clearable
                size="small"
                style="width: 220px"
                @keyup.enter="loadUsers"
                @clear="loadUsers"
              />
              <el-button size="small" :loading="loadingUsers" @click="loadUsers">搜索</el-button>
            </div>
          </div>

          <el-table :data="users" stripe size="small">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="nickname" label="昵称" min-width="120" show-overflow-tooltip />
            <el-table-column prop="phone" label="手机号" width="130" />
            <el-table-column prop="email" label="邮箱" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ row.email || '-' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
                  {{ { 1: '正常', 2: '禁用', 3: '黑名单' }[row.status] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="管理员" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.is_admin === 1" type="warning" size="small">管理员</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="task_count" label="创作数" width="80" />
            <el-table-column prop="char_count" label="总字数" width="100" />
            <el-table-column label="注册时间" width="160">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 1"
                  size="small"
                  type="danger"
                  @click="toggleUserStatus(row, 2)"
                >
                  封禁
                </el-button>
                <el-button v-else size="small" type="success" @click="toggleUserStatus(row, 1)">
                  解禁
                </el-button>
                <el-button
                  v-if="row.is_admin !== 1"
                  size="small"
                  @click="toggleUserAdmin(row, true)"
                >
                  设为管理员
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- ========== 内容管理 ========== -->
        <div v-if="activeMenu === 'contents'" class="panel">
          <div class="panel-header">
            <h3 class="panel-title">📄 内容管理</h3>
            <div class="panel-actions">
              <el-input
                v-model="contentKeyword"
                placeholder="搜索标题/主题"
                clearable
                size="small"
                style="width: 200px"
                @keyup.enter="loadContents"
                @clear="loadContents"
              />
              <el-select v-model="contentPlatform" placeholder="全部平台" clearable size="small" style="width: 120px" @change="loadContents">
                <el-option v-for="p in platforms" :key="p" :label="p" :value="p" />
              </el-select>
              <el-button size="small" :loading="loadingContents" @click="loadContents">搜索</el-button>
            </div>
          </div>

          <el-table :data="contents" stripe size="small">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="user_nickname" label="用户" width="100" show-overflow-tooltip />
            <el-table-column prop="selected_title" label="标题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="platform" label="平台" width="80" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 2 ? 'success' : 'info'" size="small">
                  {{ { 1: '生成中', 2: '完成', 3: '失败/删除' }[row.status] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="quality_score" label="质量分" width="70" />
            <el-table-column prop="content_length" label="字数" width="70" />
            <el-table-column label="创建时间" width="160">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button size="small" type="danger" @click="deleteContent(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
// 后台管理页逻辑：统计/用户/内容 三个面板切换
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import {
  getAdminStats,
  getAdminUsers,
  getAdminContents,
  updateUserStatus,
  updateUserAdmin,
  deleteAdminContent,
} from '../api/content'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const menus = [
  { key: 'stats', label: '数据总览', icon: '📊' },
  { key: 'users', label: '用户管理', icon: '👥' },
  { key: 'contents', label: '内容管理', icon: '📄' },
]
const activeMenu = ref('stats')
const platforms = ['小红书', '公众号', '知乎']

const avatarText = computed(() => (userStore.nickname || '用').charAt(0))

// 统计
const stats = ref({ total_users: 0, new_users_7d: 0, total_contents: 0, success_contents: 0, total_chars: 0, active_users_7d: 0 })

// 用户
const users = ref([])
const loadingUsers = ref(false)
const userKeyword = ref('')

// 内容
const contents = ref([])
const loadingContents = ref(false)
const contentKeyword = ref('')
const contentPlatform = ref('')

function switchMenu(key) {
  activeMenu.value = key
  if (key === 'stats') loadStats()
  if (key === 'users') loadUsers()
  if (key === 'contents') loadContents()
}

function formatChars(n) {
  if (n >= 10000) return (n / 10000).toFixed(1) + ' 万'
  return n
}

function formatTime(t) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN', { hour12: false })
}

// ---------- 统计 ----------
async function loadStats() {
  try {
    stats.value = await getAdminStats()
  } catch (e) {
    // 403 会由 axios 拦截器提示
  }
}

// ---------- 用户 ----------
async function loadUsers() {
  loadingUsers.value = true
  try {
    users.value = await getAdminUsers(userKeyword.value.trim())
  } finally {
    loadingUsers.value = false
  }
}

async function toggleUserStatus(row, status) {
  const action = status === 2 ? '封禁' : '解禁'
  try {
    await ElMessageBox.confirm(`确定${action}用户「${row.nickname}」吗？`, '提示', { type: 'warning' })
    await updateUserStatus(row.id, status)
    ElMessage.success(`已${action}`)
    loadUsers()
  } catch {
    // 取消或失败
  }
}

async function toggleUserAdmin(row, isAdmin) {
  try {
    await ElMessageBox.confirm(`确定将「${row.nickname}」设为管理员吗？`, '提示', { type: 'warning' })
    await updateUserAdmin(row.id, isAdmin)
    ElMessage.success('已设为管理员')
    loadUsers()
  } catch {
    // 取消或失败
  }
}

// ---------- 内容 ----------
async function loadContents() {
  loadingContents.value = true
  try {
    contents.value = await getAdminContents(contentKeyword.value.trim(), contentPlatform.value)
  } finally {
    loadingContents.value = false
  }
}

async function deleteContent(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.selected_title?.slice(0, 20)}」吗？`, '提示', { type: 'warning' })
    await deleteAdminContent(row.id)
    ElMessage.success('已删除')
    loadContents()
  } catch {
    // 取消或失败
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

onMounted(loadStats)
</script>

<style scoped>
.admin-page {
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
  color: #22c55e;
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

/* 布局 */
.admin-layout {
  display: flex;
  max-width: 1280px;
  margin: 24px auto;
  padding: 0 16px;
  gap: 20px;
  align-items: flex-start;
}

.admin-sidebar {
  width: 180px;
  flex-shrink: 0;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px 8px;
}

.admin-menu-item {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  color: #374151;
  cursor: pointer;
  transition: all 200ms ease-in-out;
  border-left: 3px solid transparent;
}

.admin-menu-item:hover {
  background: #f9fafb;
}

.admin-menu-item.active {
  border-left-color: #22c55e;
  background: #f0fdf4;
  color: #16a34a;
  font-weight: 500;
}

.admin-content {
  flex: 1;
  min-width: 0;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 20px 24px;
}

.panel-title {
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.panel-actions {
  display: flex;
  gap: 10px;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  text-align: center;
}

.stat-label {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #111827;
  margin-bottom: 4px;
}

.stat-sub {
  font-size: 12px;
  color: #9ca3af;
}

@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .admin-layout {
    flex-direction: column;
  }
  .admin-sidebar {
    width: 100%;
    display: flex;
    gap: 8px;
  }
  .admin-menu-item {
    flex: 1;
    text-align: center;
    border-left: none;
    border-bottom: 3px solid transparent;
  }
  .admin-menu-item.active {
    border-bottom-color: #22c55e;
  }
}
</style>
