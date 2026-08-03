<template>
  <!-- 会员中心页：当前会员状态 + 套餐购买 + 我的订单 -->
  <div class="membership-page">
    <!-- 顶部导航栏（与其他页面一致） -->
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

    <main class="main">
      <!-- ========== 当前会员状态卡片 ========== -->
      <el-card class="status-card" shadow="never">
        <div class="status-left">
          <div class="status-badge">
            <span class="badge-icon">{{ membership.plan.code === 'free' ? '🎫' : '👑' }}</span>
            <div>
              <div class="status-name">{{ membership.plan.name }}</div>
              <div class="status-sub">
                <template v-if="membership.is_active">
                  有效期至 {{ formatTime(membership.end_date) }}（剩余 {{ membership.days_left }} 天）
                </template>
                <template v-else>
                  当前为免费版，开通会员解锁全部权益
                </template>
              </div>
            </div>
          </div>
        </div>
        <div class="status-right">
          <el-button v-if="membership.is_active" type="success" plain @click="scrollToPlans">续费会员</el-button>
          <el-button v-else type="primary" @click="scrollToPlans">立即开通</el-button>
        </div>
      </el-card>

      <!-- ========== 套餐列表 ========== -->
      <div ref="plansRef" class="plans-section">
        <h3 class="section-title">选择套餐</h3>
        <div class="plans-grid">
          <div
            v-for="plan in plans"
            :key="plan.code"
            class="plan-card"
            :class="{
              'is-current': membership.is_active && membership.plan.code === plan.code,
              'is-free': plan.code === 'free',
            }"
          >
            <!-- 套餐名 + 价格 -->
            <div class="plan-header">
              <div class="plan-name">{{ plan.name }}</div>
              <div class="plan-price">
                <template v-if="plan.price_yuan > 0">
                  <span class="price-symbol">¥</span>{{ plan.price_yuan }}
                  <span class="price-period">/{{ plan.duration_days }}天</span>
                </template>
                <template v-else>免费</template>
              </div>
              <div class="plan-desc">{{ plan.description }}</div>
            </div>

            <!-- 权益清单 -->
            <ul class="plan-features">
              <li v-for="f in featureList(plan)" :key="f.label">
                <span class="feature-check">✓</span>
                <span>{{ f.label }}</span>
                <span class="feature-value">{{ f.value }}</span>
              </li>
            </ul>

            <!-- 操作按钮 -->
            <div class="plan-footer">
              <el-tag v-if="membership.is_active && membership.plan.code === plan.code" type="success" size="small">
                当前会员
              </el-tag>
              <el-button
                v-else-if="plan.code !== 'free'"
                type="primary"
                plain
                :loading="buyingPlan === plan.code"
                @click="startBuy(plan)"
              >
                {{ membership.is_active ? '升级/切换' : '立即购买' }}
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- ========== 我的订单 ========== -->
      <div class="orders-section">
        <h3 class="section-title">我的订单</h3>
        <el-table :data="orders" stripe size="small" v-loading="loadingOrders">
          <el-table-column prop="order_no" label="订单号" width="200" show-overflow-tooltip />
          <el-table-column prop="plan_name" label="套餐" width="120" />
          <el-table-column label="金额" width="100">
            <template #default="{ row }">¥{{ row.amount_yuan }}</template>
          </el-table-column>
          <el-table-column label="支付渠道" width="110">
            <template #default="{ row }">{{ channelText(row.channel) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="orderStatusType(row.status)" size="small">{{ orderStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="支付时间" width="170">
            <template #default="{ row }">{{ row.paid_at ? formatTime(row.paid_at) : '-' }}</template>
          </el-table-column>
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button v-if="row.status === 1" size="small" type="primary" @click="payOrder(row)">去支付</el-button>
              <el-button v-if="row.status === 1" size="small" @click="cancelOrder(row)">取消</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loadingOrders && !orders.length" description="暂无订单，快去开通会员吧" :image-size="80" />
      </div>
    </main>

    <!-- ========== 支付确认弹窗 ========== -->
    <el-dialog v-model="payDialogVisible" title="确认支付" width="420">
      <div class="pay-dialog-body">
        <div class="pay-plan-info">
          <span class="pay-plan-name">{{ buyingPlanObj?.name }}</span>
          <span class="pay-price">¥{{ buyingPlanObj?.price_yuan }} / {{ buyingPlanObj?.duration_days }}天</span>
        </div>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="当前为演示支付模式：微信/支付宝需商户资质，请选择「模拟支付」"
          class="pay-tip"
        />
        <el-radio-group v-model="payChannel" class="channel-group">
          <el-radio value="virtual" class="channel-radio">💳 模拟支付（立即到账）</el-radio>
          <el-radio value="wechat" class="channel-radio" disabled>微信支付（未开通）</el-radio>
          <el-radio value="alipay" class="channel-radio" disabled>支付宝（未开通）</el-radio>
        </el-radio-group>
      </div>
      <template #footer>
        <el-button @click="payDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="paying" @click="confirmPay">确认支付</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '../stores/user'
import {
  cancelOrderApi,
  createOrderApi,
  getMyMembershipApi,
  getMyOrdersApi,
  getPlansApi,
  payOrderApi,
} from '../api/membership'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// ---------- 状态 ----------
const plans = ref([]) // 套餐列表
const membership = ref({ plan: { code: 'free', name: '免费版' }, is_active: false, end_date: null, days_left: 0 })
const orders = ref([]) // 我的订单
const loadingOrders = ref(false)
const buyingPlan = ref(null) // 正在发起购买的套餐 code
const plansRef = ref(null)

// 支付弹窗
const payDialogVisible = ref(false)
const buyingPlanObj = ref(null)
const payChannel = ref('virtual')
const paying = ref(false)

// ---------- 计算属性 ----------
const avatarText = computed(() => (userStore.nickname || '用').charAt(0))

// ---------- 权益清单渲染 ----------
// 把 features 字典转成中文清单（label + value），权益字段新增时只需在这维护
const FEATURE_LABELS = {
  daily_articles: '每日文章生成',
  image_per_article: 'AI 配图（每篇）',
  batch_limit: '批量生成（单次）',
  analyze_daily: '每日逆向分析',
  export_formats: '导出格式',
  priority: '队列优先级',
}

function featureList(plan) {
  const f = plan.features || {}
  const items = []
  for (const [key, value] of Object.entries(f)) {
    const label = FEATURE_LABELS[key]
    if (!label) continue
    let text = ''
    if (Array.isArray(value)) text = value.join('、').toUpperCase()
    else if (value === -1) text = '不限'
    else if (value === 0) text = '无'
    else text = `${value}`
    items.push({ label, value: text })
  }
  return items
}

// ---------- 格式化 ----------
function formatTime(t) {
  if (!t) return '-'
  const d = new Date(t)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function channelText(ch) {
  return { virtual: '模拟支付', wechat: '微信支付', alipay: '支付宝' }[ch] || ch
}

function orderStatusText(s) {
  return { 1: '待支付', 2: '已支付', 3: '已取消', 4: '已退款' }[s] || '未知'
}

function orderStatusType(s) {
  return { 1: 'warning', 2: 'success', 3: 'info', 4: 'danger' }[s] || 'info'
}

// ---------- 数据加载 ----------
async function loadData() {
  try {
    const [plansRes, meRes, ordersRes] = await Promise.all([
      getPlansApi(),
      getMyMembershipApi(),
      getMyOrdersApi(),
    ])
    plans.value = plansRes
    membership.value = meRes
    orders.value = ordersRes
  } catch (e) {
    ElMessage.error('会员信息加载失败')
  }
}

// ---------- 购买流程 ----------
function scrollToPlans() {
  plansRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// 点击"立即购买"：先创建订单（虚拟渠道），再弹出支付确认
async function startBuy(plan) {
  buyingPlan.value = plan.code
  try {
    const order = await createOrderApi(plan.id, 'virtual')
    // 订单已创建（待支付），弹出确认框走"模拟支付"
    buyingPlanObj.value = plan
    pendingOrderNo.value = order.order_no
    payChannel.value = 'virtual'
    payDialogVisible.value = true
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '下单失败，请重试')
  } finally {
    buyingPlan.value = null
  }
}

const pendingOrderNo = ref('') // 当前弹窗对应的订单号

// 确认支付：调用模拟支付接口 → 成功后刷新会员状态和订单列表
async function confirmPay() {
  if (!pendingOrderNo.value) return
  paying.value = true
  try {
    const res = await payOrderApi(pendingOrderNo.value)
    if (res.already_paid) {
      ElMessage.info('该订单已支付')
    } else {
      ElMessage.success('支付成功，会员已开通！')
    }
    payDialogVisible.value = false
    await loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '支付失败，请重试')
  } finally {
    paying.value = false
  }
}

// 订单列表里直接"去支付"（旧订单补付）
async function payOrder(row) {
  try {
    await ElMessageBox.confirm(`确认支付订单 ${row.order_no}（¥${row.amount_yuan}）？`, '模拟支付', {
      type: 'warning',
    })
    await payOrderApi(row.order_no)
    ElMessage.success('支付成功，会员已开通！')
    await loadData()
  } catch (e) {
    if (e !== 'cancel' && !e?.response) ElMessage.error('支付失败，请重试')
  }
}

// 取消待支付订单
async function cancelOrder(row) {
  try {
    await ElMessageBox.confirm('确认取消该订单？', '取消订单', { type: 'warning' })
    await cancelOrderApi(row.order_no)
    ElMessage.success('订单已取消')
    await loadData()
  } catch (e) {
    if (e !== 'cancel' && !e?.response) ElMessage.error('取消失败，请重试')
  }
}

// ---------- 用户下拉菜单 ----------
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

onMounted(loadData)
</script>

<style scoped>
.membership-page {
  min-height: 100vh;
  background: #f5f7fa;
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

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #374151;
}

.main {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px 16px 48px;
}

/* 会员状态卡片 */
.status-card {
  margin-bottom: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-radius: 12px;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 12px;
}

.badge-icon {
  font-size: 36px;
}

.status-name {
  font-size: 20px;
  font-weight: 700;
  color: #111827;
}

.status-sub {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}

/* 套餐区域 */
.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
  margin: 24px 0 16px;
}

.plans-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.plan-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.2s, transform 0.2s;
}

.plan-card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.plan-card.is-current {
  border-color: #22c55e;
  box-shadow: 0 0 0 1px #22c55e inset;
}

.plan-card.is-free {
  background: #fafafa;
}

.plan-header {
  text-align: center;
  padding-bottom: 16px;
  border-bottom: 1px dashed #e5e7eb;
}

.plan-name {
  font-size: 17px;
  font-weight: 700;
  color: #111827;
}

.plan-price {
  font-size: 32px;
  font-weight: 800;
  color: #111827;
  margin: 8px 0 4px;
}

.price-symbol {
  font-size: 18px;
  vertical-align: 12px;
  color: #22c55e;
}

.price-period {
  font-size: 13px;
  font-weight: 400;
  color: #9ca3af;
}

.plan-desc {
  font-size: 12px;
  color: #9ca3af;
  min-height: 32px;
}

/* 权益清单 */
.plan-features {
  list-style: none;
  margin: 16px 0;
  padding: 0;
  flex: 1;
}

.plan-features li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #4b5563;
  padding: 5px 0;
}

.feature-check {
  color: #22c55e;
  font-weight: 700;
}

.feature-value {
  margin-left: auto;
  color: #111827;
  font-weight: 600;
}

.plan-footer {
  text-align: center;
  min-height: 32px;
}

/* 订单区域 */
.orders-section {
  margin-top: 8px;
}

/* 支付弹窗 */
.pay-dialog-body {
  padding: 0 4px;
}

.pay-plan-info {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 15px;
  margin-bottom: 12px;
}

.pay-plan-name {
  font-weight: 700;
}

.pay-price {
  color: #22c55e;
  font-weight: 700;
}

.pay-tip {
  margin-bottom: 12px;
}

.channel-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.channel-radio {
  margin-right: 0;
}

/* 响应式 */
@media (max-width: 900px) {
  .plans-grid {
    grid-template-columns: 1fr;
  }
}
</style>
