// 会员中心购买流程实测：登录 → 会员中心 → 购买专业版 → 模拟支付 → 验证会员状态
const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8002'
const API = 'http://127.0.0.1:8001'

async function main() {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`) })

  // 注册一个全新的 199 测试用户（确保干净的免费用户状态）
  const phone = '199' + String(Date.now()).slice(-8)
  console.log('测试账号:', phone)
  await page.goto(`${BASE}/register`)
  await page.fill('input[placeholder*="手机号"], input[placeholder*="注册手机号"]', phone)
  await page.fill('input[placeholder*="昵称"]', `会员测试${phone.slice(-4)}`)
  await page.fill('input[placeholder*="密码"]', 'test123456')
  await page.fill('input[placeholder*="确认密码"]', 'test123456')
  await page.click('button.submit-btn')
  await page.waitForURL('**/', { timeout: 15000 })
  console.log('✓ 注册并登录成功')

  // 进入会员中心
  await page.click('text=会员中心')
  await page.waitForURL('**/membership', { timeout: 10000 })
  await page.waitForSelector('text=选择套餐', { timeout: 15000 })
  console.log('✓ 会员中心页面打开')

  // 验证当前是免费版
  const freeStatus = await page.textContent('.status-name')
  console.log('当前会员状态:', freeStatus.trim())

  // 点击专业版"立即购买"
  await page.click('.plan-card:has-text("专业版") button:has-text("立即购买")')
  await page.waitForSelector('.el-dialog:visible', { timeout: 10000 })
  await page.waitForTimeout(500)
  const dialogText = await page.textContent('.el-dialog')
  console.log('支付弹窗内容:', dialogText.replace(/\s+/g, ' ').trim().slice(0, 120))

  // 确认支付（默认选中模拟支付）
  await page.click('.el-dialog button:has-text("确认支付")')
  await page.waitForSelector('.el-message--success', { timeout: 10000 })
  console.log('✓ 支付成功提示出现')

  // 等待订单和会员状态刷新
  await page.waitForTimeout(1500)
  const newStatus = await page.textContent('.status-name')
  const statusSub = await page.textContent('.status-sub')
  console.log('支付后会员状态:', newStatus.trim(), '|', statusSub.replace(/\s+/g, ' ').trim())

  // 验证订单列表有已支付订单
  const orderRows = await page.$$('.orders-section .el-table__row')
  console.log('订单列表行数:', orderRows.length)
  const firstRowText = orderRows.length ? (await orderRows[0].textContent()).replace(/\s+/g, ' ') : ''
  console.log('第一笔订单:', firstRowText)

  // 验证"当前会员"标签出现在专业版卡片
  const proCard = await page.textContent('.plan-card:has-text("专业版")')
  console.log('专业版卡片含当前会员标签:', proCard.includes('当前会员'))

  // 验证后端会员接口数据
  const token = await page.evaluate(() => localStorage.getItem('token'))
  const meRes = await page.request.get(`${API}/api/v1/membership/me`, { headers: { Authorization: `Bearer ${token}` } })
  const me = await meRes.json()
  console.log('后端 /me:', JSON.stringify({ plan: me.plan.code, is_active: me.is_active, days_left: me.days_left }))

  // 截图
  await page.screenshot({ path: 'frontend/scripts/verify_membership.png', fullPage: true })
  console.log('✓ 截图已保存')

  console.log('页面错误:', errors.length ? errors : '无')
  await browser.close()
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1) })
