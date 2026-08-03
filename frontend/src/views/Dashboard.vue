<template>
  <!-- 数据看板页：创作统计概览 + 趋势/平台/质量图表 -->
  <div class="dashboard-page">
    <!-- 顶部导航栏（与工作台一致） -->
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
      <!-- 时间范围切换 -->
      <div class="toolbar">
        <h2 class="page-title">📊 数据看板</h2>
        <el-radio-group v-model="days" size="small" @change="loadData">
          <el-radio-button :value="7">近 7 天</el-radio-button>
          <el-radio-button :value="30">近 30 天</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 概览卡片 -->
      <div class="summary-grid">
        <el-card class="summary-card">
          <div class="summary-label">📝 总创作</div>
          <div class="summary-value">{{ summary.total_count }}</div>
          <div class="summary-sub">篇已发布内容</div>
        </el-card>
        <el-card class="summary-card">
          <div class="summary-label">🔤 总字数</div>
          <div class="summary-value">{{ formatChars(summary.total_chars) }}</div>
          <div class="summary-sub">累计输出文字</div>
        </el-card>
        <el-card class="summary-card">
          <div class="summary-label">⏱️ 节省时间</div>
          <div class="summary-value">{{ summary.saved_hours }}</div>
          <div class="summary-sub">小时（按每篇 2 小时估算）</div>
        </el-card>
        <el-card class="summary-card">
          <div class="summary-label">⭐ 平均质量分</div>
          <div class="summary-value">{{ summary.avg_quality }}</div>
          <div class="summary-sub">共 {{ summary.failed_count }} 次失败</div>
        </el-card>
      </div>

      <!-- 图表区 -->
      <div class="charts-grid">
        <el-card class="chart-card">
          <template #header>
            <span>📈 创作趋势（近 {{ days }} 天）</span>
          </template>
          <div ref="trendRef" class="chart"></div>
        </el-card>

        <el-card class="chart-card">
          <template #header>
            <span>🍩 平台分布</span>
          </template>
          <div ref="platformRef" class="chart"></div>
        </el-card>

        <el-card class="chart-card full">
          <template #header>
            <span>🏆 质量分布</span>
          </template>
          <div ref="qualityRef" class="chart"></div>
        </el-card>
      </div>

      <!-- 空状态 -->
      <el-empty v-if="!loading && !summary.total_count" description="还没有创作记录，去生成第一篇爆文吧！">
        <el-button type="primary" @click="router.push('/')">去创作</el-button>
      </el-empty>
    </main>
  </div>
</template>

<script setup>
// 数据看板：加载统计 → ECharts 渲染图表
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import { getDashboardOverview } from '../api/content'
import * as echarts from 'echarts'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const days = ref(30)
const loading = ref(false)
const summary = ref({ total_count: 0, total_chars: 0, avg_quality: 0, failed_count: 0, saved_hours: 0 })

// 图表容器
const trendRef = ref(null)
const platformRef = ref(null)
const qualityRef = ref(null)

// ECharts 实例
let trendChart = null
let platformChart = null
let qualityChart = null

const avatarText = computed(() => (userStore.nickname || '用').charAt(0))

// 字数格式化（万）
function formatChars(n) {
  if (n >= 10000) return (n / 10000).toFixed(1) + ' 万'
  return n
}

// ---------- 加载数据 ----------
async function loadData() {
  loading.value = true
  try {
    const data = await getDashboardOverview(days.value)
    summary.value = data.summary
    await nextTick()
    renderCharts(data)
  } catch (e) {
    // 错误已由 axios 拦截器统一提示
  } finally {
    loading.value = false
  }
}

// ---------- 渲染图表 ----------
function renderCharts(data) {
  // 1. 趋势折线图
  if (trendChart) trendChart.dispose()
  trendChart = echarts.init(trendRef.value)
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: data.trend.map((t) => t.date.slice(5)), // MM-DD
      axisLabel: { fontSize: 10 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '创作篇数',
        type: 'line',
        smooth: true,
        data: data.trend.map((t) => t.count),
        areaStyle: { opacity: 0.15 },
        itemStyle: { color: '#22c55e' },
        lineStyle: { color: '#22c55e', width: 2 },
      },
    ],
  })

  // 2. 平台分布饼图
  if (platformChart) platformChart.dispose()
  platformChart = echarts.init(platformRef.value)
  platformChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, icon: 'circle' },
    series: [
      {
        name: '平台分布',
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['50%', '45%'],
        data: data.platforms.map((p) => ({ name: p.platform, value: p.count })),
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        color: ['#22c55e', '#4ade80', '#86efac', '#16a34a', '#0f9d58'],
        label: { fontSize: 12 },
      },
    ],
  })

  // 3. 质量分布柱状图
  if (qualityChart) qualityChart.dispose()
  qualityChart = echarts.init(qualityRef.value)
  qualityChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: data.quality_dist.map((q) => q.range),
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '篇数',
        type: 'bar',
        data: data.quality_dist.map((q) => q.count),
        itemStyle: { color: '#22c55e', borderRadius: [6, 6, 0, 0] },
        barWidth: 40,
      },
    ],
  })
}

// 窗口缩放时自适应
function handleResize() {
  trendChart?.resize()
  platformChart?.resize()
  qualityChart?.resize()
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

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  platformChart?.dispose()
  qualityChart?.dispose()
})
</script>

<style scoped>
.dashboard-page {
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

.main {
  max-width: 1100px;
  margin: 24px auto;
  padding: 0 16px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #111827;
}

/* 概览卡片 */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.summary-card {
  text-align: center;
}

.summary-label {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 8px;
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
  color: #111827;
  margin-bottom: 4px;
}

.summary-sub {
  font-size: 12px;
  color: #9ca3af;
}

/* 图表 */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.chart-card.full {
  grid-column: 1 / -1;
}

.chart {
  height: 320px;
}

/* 响应式 */
@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .charts-grid {
    grid-template-columns: 1fr;
  }
  .chart-card.full {
    grid-column: auto;
  }
}

@media (max-width: 480px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
