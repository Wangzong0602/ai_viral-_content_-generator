// 到期提醒实测：临期提醒条 / 过期提醒条 / 工作台提示 / 管理端续期
const { chromium } = require('playwright')
const { execSync } = require('child_process')

const BASE = 'http://127.0.0.1:8002'
const API = 'http://127.0.0.1:8001'
const PY = '"E:\\miniconda3\\envs\\fastapi_env\\python.exe"'

function setExpiry(userId, mode) {
  execSync(`${PY} "C:\\Users\\ADMINI~1\\AppData\\Local\\Temp\\opencode\\set_expiry.py" ${userId} ${mode}`, { stdio: 'pipe' })
}

async function main() {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))

  // 准备：API 注册测试用户 + 管理员开通 30 天
  const phone = '199' + String(Date.now()).slice(-8)
  const regRes = await fetch(`${API}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, password: 'test123456', nickname: `临期测${phone.slice(-4)}` }),
  })
  const reg = await regRes.json()
  const userId = reg.user.id
  const adminLoginRes = await fetch(`${API}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account: '19900000001', password: 'admin123456' }),
  })
  const adminLogin = await adminLoginRes.json()
  await fetch(`${API}/api/v1/admin/users/${userId}/membership`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${adminLogin.access_token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_id: 1 }),
  })

  // 模拟临期：到期时间改到 2 天后
  setExpiry(userId, 'expiring')

  // 1. 登录 → 工作台应弹临期提示
  await page.goto(`${BASE}/login`)
  await page.fill('input[placeholder*="手机号"]', phone)
  await page.fill('input[placeholder*="密码"]', 'test123456')
  await page.click('button[type="submit"], .submit-btn, button:has-text("登 录"), button:has-text("登录")')
  await page.waitForURL('**/', { timeout: 15000 })
  await page.waitForSelector('.el-message--warning', { timeout: 10000 })
  const tip1 = await page.textContent('.el-message--warning')
  console.log('1.工作台临期提示:', tip1.replace(/\s+/g, ' ').trim().slice(0, 60))
  await page.waitForTimeout(3000) // 等 message 消失

  // 2. 会员中心临期提醒条
  await page.goto(`${BASE}/membership`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.expiry-alert', { timeout: 10000 })
  const alert1 = await page.textContent('.expiry-alert')
  console.log('2.会员中心临期提醒条:', alert1.replace(/\s+/g, ' ').trim().slice(0, 80))

  // 3. 模拟过期 → 会员中心过期提醒条
  setExpiry(userId, 'expired')
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForSelector('.expiry-alert', { timeout: 10000 })
  const alert2 = await page.textContent('.expiry-alert')
  console.log('3.会员中心过期提醒条:', alert2.replace(/\s+/g, ' ').trim().slice(0, 80))
  await page.screenshot({ path: 'frontend/scripts/verify_expiry_alert.png', fullPage: true })

  // 4. 管理端续期：重新登录管理员 → 用户管理 → 找到该用户 → 续期 → 会员列更新
  //    （注意：必须用管理员会话访问后台，普通用户访问会 403；已登录用户访问 /login 会被路由守卫重定向，先清登录态）
  await page.goto(`${BASE}/`)
  await page.evaluate(() => localStorage.clear())
  await page.goto(`${BASE}/login`)
  await page.fill('input[placeholder*="手机号"]', '19900000001')
  await page.fill('input[placeholder*="密码"]', 'admin123456')
  await page.click('button[type="submit"], .submit-btn, button:has-text("登 录"), button:has-text("登录")')
  await page.waitForURL('**/', { timeout: 15000 })
  await page.goto(`${BASE}/admin`, { waitUntil: 'networkidle' })
  await page.click('.admin-menu-item:has-text("用户管理")')
  await page.waitForSelector('.el-table__row', { timeout: 10000 })
  await page.waitForTimeout(1500)
  const row = page.locator(`.el-table__row:has-text("${phone}")`)
  const rowCount = await row.count()
  console.log('   匹配行数:', rowCount)
  const rowText = await row.first().textContent().catch(() => '(无)')
  console.log('   行内容:', rowText.replace(/\s+/g, ' ').trim().slice(0, 90))
  await row.first().locator('button:has-text("续期")').click()
  await page.waitForSelector('.el-dialog:visible', { timeout: 5000 })
  await page.waitForTimeout(300)
  await page.click('.el-dialog .el-select')
  await page.waitForTimeout(400)
  await page.click('.el-select-dropdown__item:has-text("专业版")')
  await page.click('.el-dialog button:has-text("确认开通")')
  await page.waitForSelector('.el-message--success', { timeout: 8000 })
  console.log('4.管理端续期成功提示 ✓')
  await page.waitForTimeout(1000)
  const rowTextAfter = await page.locator(`.el-table__row:has-text("${phone}")`).textContent()
  console.log('   续期后会员列含专业版:', rowTextAfter.includes('专业版'))
  await page.screenshot({ path: 'frontend/scripts/verify_grant.png', fullPage: true })

  // 5. 用户端确认：重新登录该用户 → me 接口 active
  const meRes = await fetch(`${API}/api/v1/membership/me`, {
    headers: { Authorization: `Bearer ${reg.access_token}` },
  })
  const me = await meRes.json()
  console.log('5.用户 me 恢复:', JSON.stringify({ plan: me.plan.code, active: me.is_active, days_left: me.days_left }))

  console.log('页面错误:', errors.length ? errors : '无')
  await browser.close()
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1) })
