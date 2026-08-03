// 后台管理：套餐管理 + 订单管理 + 用户会员列 实测
const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8002'

async function main() {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))

  // 登录管理员
  await page.goto(`${BASE}/login`)
  await page.fill('input[placeholder*="手机号"]', '19900000001')
  await page.fill('input[placeholder*="密码"]', 'admin123456')
  await page.click('button[type="submit"], .submit-btn, button:has-text("登 录"), button:has-text("登录")')
  await page.waitForURL('**/', { timeout: 15000 })

  // 进入后台管理
  await page.click('text=后台管理')
  await page.waitForURL('**/admin', { timeout: 10000 })
  await page.waitForSelector('text=数据总览', { timeout: 10000 })
  console.log('✓ 后台管理打开')

  // 数据总览：检查新增的订单/金额卡片
  const statsText = await page.textContent('.stats-grid')
  console.log('统计卡含订单/金额:', statsText.includes('已支付订单') && statsText.includes('实收金额'))

  // 用户管理：检查会员列
  await page.click('.admin-menu-item:has-text("用户管理")')
  await page.waitForTimeout(800)
  const userTableText = await page.textContent('.admin-content')
  console.log('用户表含会员列:', userTableText.includes('会员'))

  // 套餐管理：列表
  await page.click('.admin-menu-item:has-text("套餐管理")')
  await page.waitForTimeout(800)
  const plansText = await page.textContent('.admin-content')
  console.log('套餐列表含三档:', plansText.includes('专业版') && plansText.includes('企业版') && plansText.includes('免费版'))

  // 新增套餐
  await page.click('button:has-text("新增套餐")')
  await page.waitForSelector('.el-dialog:visible', { timeout: 5000 })
  await page.fill('.el-dialog input[placeholder*="如 pro"]', 'week')
  await page.fill('.el-dialog input[placeholder*="如 专业版"]', '周体验版')
  await page.fill('.el-dialog textarea', '{"daily_articles":20}')
  await page.click('.el-dialog button:has-text("保存")')
  await page.waitForSelector('.el-message--success', { timeout: 8000 })
  console.log('✓ 新增套餐成功')
  await page.waitForTimeout(800)
  const plansAfter = await page.textContent('.admin-content')
  console.log('列表出现周体验版:', plansAfter.includes('周体验版'))

  // 编辑套餐（改价格为 49）
  await page.click('.el-table__row:has-text("周体验版") button:has-text("编辑")')
  await page.waitForSelector('.el-dialog:visible', { timeout: 5000 })
  await page.waitForTimeout(300)
  await page.fill('.el-dialog .el-input-number input', '49')
  await page.click('.el-dialog button:has-text("保存")')
  await page.waitForSelector('.el-message--success', { timeout: 8000 })
  console.log('✓ 编辑套餐成功')

  // 下架套餐
  await page.click('.el-table__row:has-text("周体验版") button:has-text("下架")')
  await page.waitForSelector('.el-message-box:visible', { timeout: 5000 })
  await page.click('.el-message-box button:has-text("确定")')
  await page.waitForSelector('.el-message--success', { timeout: 8000 })
  console.log('✓ 下架套餐成功')

  // 订单管理：列表
  await page.click('.admin-menu-item:has-text("订单管理")')
  await page.waitForTimeout(800)
  const ordersText = await page.textContent('.admin-content')
  console.log('订单列表有数据:', ordersText.includes('专业版') || ordersText.includes('模拟支付'))

  // 筛选已支付订单
  await page.click('.panel-actions .el-select')
  await page.waitForTimeout(500)
  await page.click('.el-select-dropdown__item:has-text("已支付")')
  await page.waitForTimeout(800)
  const filteredText = await page.textContent('.admin-content')
  console.log('筛选已支付订单正常:', filteredText.includes('已支付'))

  await page.screenshot({ path: 'frontend/scripts/verify_admin_membership.png', fullPage: true })
  console.log('✓ 截图已保存')
  console.log('页面错误:', errors.length ? errors : '无')
  await browser.close()
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1) })
