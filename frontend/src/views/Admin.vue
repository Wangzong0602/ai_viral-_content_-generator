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
          <el-menu-item index="/membership">会员中心</el-menu-item>
          <el-menu-item v-if="userStore.user?.is_admin === 1" index="/admin">后台管理</el-menu-item>
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
              <el-dropdown-item command="membership">会员中心</el-dropdown-item>
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
            <el-card class="stat-card">
              <div class="stat-label">已支付订单</div>
              <div class="stat-value">{{ stats.paid_orders }}</div>
              <div class="stat-sub">共 {{ stats.total_orders }} 笔</div>
            </el-card>
            <el-card class="stat-card">
              <div class="stat-label">实收金额</div>
              <div class="stat-value">¥{{ stats.paid_amount_yuan }}</div>
              <div class="stat-sub">演示支付累计</div>
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
            <el-table-column label="会员" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.plan_name !== '免费版'" type="warning" size="small">
                  {{ row.plan_name }}
                </el-tag>
                <span v-else class="free-text">免费版</span>
              </template>
            </el-table-column>
            <el-table-column label="会员到期" width="110">
              <template #default="{ row }">
                <span v-if="row.membership_end" class="muted-text">{{ row.membership_end.slice(0, 10) }}</span>
                <span v-else>-</span>
              </template>
            </el-table-column>
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
                <el-button size="small" type="success" @click="openGrantDialog(row)">
                  续期
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

        <!-- ========== 套餐管理 ========== -->
        <div v-if="activeMenu === 'plans'" class="panel">
          <div class="panel-header">
            <h3 class="panel-title">💎 套餐管理</h3>
            <div class="panel-actions">
              <el-button size="small" type="primary" @click="openPlanDialog()">新增套餐</el-button>
            </div>
          </div>

          <el-table :data="plans" stripe size="small">
            <el-table-column prop="code" label="标识" width="110" />
            <el-table-column prop="name" label="套餐名" width="120" />
            <el-table-column label="价格" width="110">
              <template #default="{ row }">
                <template v-if="row.price_yuan > 0">¥{{ row.price_yuan }} / {{ row.duration_days }}天</template>
                <template v-else>免费</template>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="介绍" min-width="180" show-overflow-tooltip />
            <el-table-column prop="sort_order" label="排序" width="70" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
                  {{ row.status === 1 ? '上架' : '下架' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button v-if="row.code !== 'free'" size="small" @click="openPlanDialog(row)">编辑</el-button>
                <el-button v-if="row.status === 1 && row.code !== 'free'" size="small" type="danger" @click="deletePlan(row)">下架</el-button>
                <el-button v-if="row.status === 2 && row.code !== 'free'" size="small" type="success" @click="togglePlanStatus(row, 1)">上架</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- ========== 订单管理 ========== -->
        <div v-if="activeMenu === 'orders'" class="panel">
          <div class="panel-header">
            <h3 class="panel-title">🧾 订单管理</h3>
            <div class="panel-actions">
              <el-select v-model="orderStatus" placeholder="全部状态" clearable size="small" style="width: 120px" @change="loadOrders">
                <el-option v-for="(label, val) in orderStatusMap" :key="val" :label="label" :value="Number(val)" />
              </el-select>
              <el-input
                v-model="orderKeyword"
                placeholder="搜索订单号/套餐名"
                clearable
                size="small"
                style="width: 200px"
                @keyup.enter="loadOrders"
                @clear="loadOrders"
              />
              <el-button size="small" :loading="loadingOrders" @click="loadOrders">搜索</el-button>
            </div>
          </div>

          <el-table :data="orders" stripe size="small">
            <el-table-column prop="order_no" label="订单号" width="190" show-overflow-tooltip />
            <el-table-column prop="user_nickname" label="用户" width="100" show-overflow-tooltip />
            <el-table-column prop="plan_name" label="套餐" width="110" />
            <el-table-column label="金额" width="90">
              <template #default="{ row }">¥{{ row.amount_yuan }}</template>
            </el-table-column>
            <el-table-column label="渠道" width="100">
              <template #default="{ row }">{{ { virtual: '模拟支付', wechat: '微信', alipay: '支付宝' }[row.channel] || row.channel }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="orderStatusType(row.status)" size="small">{{ orderStatusMap[row.status] }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="支付时间" width="160">
              <template #default="{ row }">{{ row.paid_at ? formatTime(row.paid_at) : '-' }}</template>
            </el-table-column>
            <el-table-column label="创建时间" width="160">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </main>
    </div>

    <!-- ========== 套餐编辑弹窗 ========== -->
    <el-dialog v-model="planDialogVisible" :title="editingPlan ? '编辑套餐' : '新增套餐'" width="520">
      <el-form :model="planForm" label-width="90px">
        <el-form-item label="套餐标识" required>
          <el-input v-model="planForm.code" placeholder="如 pro（唯一，创建后不可改）" :disabled="!!editingPlan" />
        </el-form-item>
        <el-form-item label="套餐名称" required>
          <el-input v-model="planForm.name" placeholder="如 专业版" />
        </el-form-item>
        <el-form-item label="价格（元）" required>
          <el-input-number v-model="planForm.price_yuan" :min="0" :precision="2" :step="10" />
        </el-form-item>
        <el-form-item label="有效期（天）">
          <el-input-number v-model="planForm.duration_days" :min="1" :max="3650" :step="30" />
        </el-form-item>
        <el-form-item label="介绍">
          <el-input v-model="planForm.description" type="textarea" :rows="2" placeholder="一句话介绍，展示在套餐卡片上" />
        </el-form-item>
        <el-form-item label="排序权重">
          <el-input-number v-model="planForm.sort_order" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="planForm.status">
            <el-radio :value="1">上架</el-radio>
            <el-radio :value="2">下架</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="权益配置">
          <el-input
            v-model="planForm.featuresText"
            type="textarea"
            :rows="5"
            placeholder='JSON 格式，如：{"daily_articles":100,"image_per_article":10,"batch_limit":50,"analyze_daily":50,"export_formats":["txt","md","html"],"priority":"优先队列"}（-1 表示不限，0 表示无）'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingPlan" @click="savePlan">保存</el-button>
      </template>
    </el-dialog>

    <!-- ========== 会员续期弹窗 ========== -->
    <el-dialog v-model="grantDialogVisible" :title="`会员续期 - ${grantUser?.nickname || ''}`" width="420">
      <el-form label-width="90px">
        <el-form-item label="目标套餐" required>
          <el-select v-model="grantForm.planId" placeholder="选择套餐" style="width: 100%">
            <el-option v-for="p in grantablePlans" :key="p.id" :label="`${p.name}（¥${p.price_yuan}/${p.duration_days}天）`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="赠送天数">
          <el-input-number v-model="grantForm.days" :min="1" :max="3650" :step="30" placeholder="默认套餐有效期" />
          <span class="muted-text" style="margin-left: 8px">留空 = 套餐默认天数</span>
        </el-form-item>
      </el-form>
      <div class="muted-text" style="margin: 0 0 12px 90px">
        {{ grantUser?.plan_name || '免费版' }}
        <template v-if="grantUser?.membership_end">，到期 {{ grantUser.membership_end.slice(0, 10) }}</template>
        <template v-else>（当前无有效会员）</template>
      </div>
      <template #footer>
        <el-button @click="grantDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="granting" @click="confirmGrant">确认开通</el-button>
      </template>
    </el-dialog>
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
  getAdminPlans,
  createAdminPlan,
  updateAdminPlan,
  deleteAdminPlan,
  getAdminOrders,
  grantMembership,
} from '../api/content'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const menus = [
  { key: 'stats', label: '数据总览', icon: '📊' },
  { key: 'users', label: '用户管理', icon: '👥' },
  { key: 'contents', label: '内容管理', icon: '📄' },
  { key: 'plans', label: '套餐管理', icon: '💎' },
  { key: 'orders', label: '订单管理', icon: '🧾' },
]
const activeMenu = ref('stats')
const platforms = ['小红书', '公众号', '知乎', 'B站', '快手', '视频号']

const avatarText = computed(() => (userStore.nickname || '用').charAt(0))

// 统计
const stats = ref({ total_users: 0, new_users_7d: 0, total_contents: 0, success_contents: 0, total_chars: 0, active_users_7d: 0, total_orders: 0, paid_orders: 0, paid_amount_yuan: 0 })

// 用户
const users = ref([])
const loadingUsers = ref(false)
const userKeyword = ref('')

// 内容
const contents = ref([])
const loadingContents = ref(false)
const contentKeyword = ref('')
const contentPlatform = ref('')

// 套餐管理
const plans = ref([])
const planDialogVisible = ref(false)
const editingPlan = ref(null)
const savingPlan = ref(false)
const planForm = ref({
  code: '',
  name: '',
  price_yuan: 199,
  duration_days: 30,
  description: '',
  sort_order: 1,
  status: 1,
  featuresText: '',
})

// 订单管理
const orders = ref([])
const loadingOrders = ref(false)
const orderKeyword = ref('')
const orderStatus = ref('')
const orderStatusMap = { 1: '待支付', 2: '已支付', 3: '已取消', 4: '已退款' }

// 会员续期
const grantDialogVisible = ref(false)
const grantUser = ref(null) // 要续期的用户行
const granting = ref(false)
const grantForm = ref({ planId: null, days: null })
const grantablePlans = computed(() => plans.value.filter((p) => p.code !== 'free' && p.status === 1))

function switchMenu(key) {
  activeMenu.value = key
  if (key === 'stats') loadStats()
  if (key === 'users') loadUsers()
  if (key === 'contents') loadContents()
  if (key === 'plans') loadPlans()
  if (key === 'orders') loadOrders()
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

// ---------- 套餐管理 ----------
async function loadPlans() {
  try {
    plans.value = await getAdminPlans()
  } catch {
    // 403 已由拦截器提示
  }
}

function orderStatusType(s) {
  return { 1: 'warning', 2: 'success', 3: 'info', 4: 'danger' }[s] || 'info'
}

// 打开新增/编辑弹窗（编辑时回填表单）
function openPlanDialog(plan = null) {
  editingPlan.value = plan
  if (plan) {
    planForm.value = {
      code: plan.code,
      name: plan.name,
      price_yuan: plan.price_yuan,
      duration_days: plan.duration_days,
      description: plan.description,
      sort_order: plan.sort_order,
      status: plan.status,
      featuresText: JSON.stringify(plan.features || {}, null, 2),
    }
  } else {
    planForm.value = { code: '', name: '', price_yuan: 199, duration_days: 30, description: '', sort_order: 1, status: 1, featuresText: '' }
  }
  planDialogVisible.value = true
}

// 保存套餐（新增或编辑）：featuresText 是 JSON 字符串，需解析校验
async function savePlan() {
  const f = planForm.value
  if (!f.code.trim() || !f.name.trim()) {
    ElMessage.warning('请填写套餐标识和名称')
    return
  }
  let features = {}
  if (f.featuresText.trim()) {
    try {
      features = JSON.parse(f.featuresText)
    } catch {
      ElMessage.error('权益配置不是合法 JSON，请检查格式')
      return
    }
  }
  savingPlan.value = true
  try {
    const payload = {
      code: f.code.trim(),
      name: f.name.trim(),
      price_yuan: f.price_yuan,
      duration_days: f.duration_days,
      description: f.description,
      sort_order: f.sort_order,
      status: f.status,
      features,
    }
    if (editingPlan.value) {
      // 编辑时 code 不能改，去掉 code 字段（后端忽略也行，明确一点）
      delete payload.code
      await updateAdminPlan(editingPlan.value.id, payload)
      ElMessage.success('套餐已更新')
    } else {
      await createAdminPlan(payload)
      ElMessage.success('套餐已创建')
    }
    planDialogVisible.value = false
    loadPlans()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    savingPlan.value = false
  }
}

// 下架套餐
async function deletePlan(row) {
  try {
    await ElMessageBox.confirm(`确定下架套餐「${row.name}」吗？下架后用户不可再购买。`, '提示', { type: 'warning' })
    await deleteAdminPlan(row.id)
    ElMessage.success('已下架')
    loadPlans()
  } catch {
    // 取消或失败
  }
}

// 上架/下架切换（编辑弹窗里也可改，这里提供快捷操作）
async function togglePlanStatus(row, status) {
  try {
    await updateAdminPlan(row.id, { status })
    ElMessage.success(status === 1 ? '已上架' : '已下架')
    loadPlans()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

// ---------- 订单管理 ----------
async function loadOrders() {
  loadingOrders.value = true
  try {
    orders.value = await getAdminOrders({
      status: orderStatus.value,
      keyword: orderKeyword.value.trim(),
    })
  } finally {
    loadingOrders.value = false
  }
}

// ---------- 会员续期 ----------
// 打开续期弹窗：先确保套餐列表已加载（选套餐下拉用）
async function openGrantDialog(row) {
  grantUser.value = row
  grantForm.value = { planId: null, days: null }
  if (!plans.value.length) {
    try { plans.value = await getAdminPlans() } catch { /* 忽略 */ }
  }
  grantDialogVisible.value = true
}

async function confirmGrant() {
  if (!grantForm.value.planId) {
    ElMessage.warning('请选择套餐')
    return
  }
  granting.value = true
  try {
    const res = await grantMembership(grantUser.value.id, grantForm.value.planId, grantForm.value.days)
    ElMessage.success(res.message || '已开通')
    grantDialogVisible.value = false
    loadUsers() // 刷新用户列表（会员列更新）
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '开通失败')
  } finally {
    granting.value = false
  }
}

// ---------- 用户菜单 ----------
function handleUserCommand(command) {
  if (command === 'membership') {
    router.push('/membership')
    return
  }
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

/* 用户列表会员列辅助样式 */
.free-text {
  color: #9ca3af;
  font-size: 12px;
}

.muted-text {
  color: #9ca3af;
  font-size: 12px;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);  gap: 16px;
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
