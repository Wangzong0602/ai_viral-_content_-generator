// 权益配额前端实测：配额提示条 + 会员中心用量面板 + 超限拦截提示
const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8002'

async function main() {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))

  // 注册新免费用户
  const phone = '199' + String(Date.now()).slice(-8)
  await page.goto(`${BASE}/register`)
  await page.fill('input[placeholder*="手机号"]', phone)
  await page.fill('input[placeholder*="昵称"]', `配额${phone.slice(-4)}`)
  await page.fill('input[placeholder*="密码"]', 'test123456')
  await page.fill('input[placeholder*="确认密码"]', 'test123456')
  await page.click('button.submit-btn')
  await page.waitForURL('**/', { timeout: 15000 })

  // 1. 工作台配额提示条
  await page.waitForSelector('.quota-tip', { timeout: 10000 })
  const tipText = await page.textContent('.quota-tip')
  console.log('工作台配额提示:', tipText.replace(/\s+/g, ' ').trim())

  // 2. 会员中心今日用量面板（等待接口数据渲染完成：出现"剩余 3"而非初始 0/0）
  await page.click('text=会员中心')
  await page.waitForURL('**/membership', { timeout: 10000 })
  await page.waitForSelector('.quota-grid', { timeout: 10000 })
  await page.waitForFunction(
    () => document.querySelector('.quota-grid')?.textContent.includes('剩余 3'),
    { timeout: 10000 }
  )
  const quotaText = await page.textContent('.quota-grid')
  console.log('会员中心用量面板:', quotaText.replace(/\s+/g, ' ').trim().slice(0, 200))

  // 3. 用 API 直接消耗完 3 次文章配额，再点生成看前端拦截提示
  const token = await page.evaluate(() => localStorage.getItem('token'))
  const API = 'http://127.0.0.1:8001'
  for (let i = 0; i < 3; i++) {
    await fetch(`${API}/api/v1/content/topics`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ keyword: '配额测试主题', platform: '小红书' }),
    })
  }
  // 第 4 次在页面上点"生成选题"
  await page.goto(`${BASE}/`)
  await page.waitForTimeout(800)
  await page.fill('.input-card input[placeholder*="主题"]', '配额测试主题')
  await page.click('button:has-text("一键生成")')
  await page.waitForSelector('.el-message--error', { timeout: 10000 })
  const errMsg = await page.textContent('.el-message--error')
  console.log('超限拦截提示:', errMsg.replace(/\s+/g, ' ').trim())

  // 4. 配额提示条应变为红色警告（remaining=0）
  await page.waitForTimeout(500)
  const warn = await page.$('.quota-tip-warn')
  console.log('配额用尽红色警告:', !!warn)

  await page.screenshot({ path: 'frontend/scripts/verify_quota.png', fullPage: true })
  console.log('✓ 截图已保存')
  console.log('页面错误:', errors.length ? errors : '无')
  await browser.close()
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1) })
