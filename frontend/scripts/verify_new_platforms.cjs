// 新平台前端验证：平台下拉 6 个 + B站模板联动
const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8002'

async function main() {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))

  await page.goto(`${BASE}/login`)
  await page.fill('input[placeholder*="手机号"]', '19900000001')
  await page.fill('input[placeholder*="密码"]', 'admin123456')
  await page.click('button[type="submit"], .submit-btn, button:has-text("登 录"), button:has-text("登录")')
  await page.waitForURL('**/', { timeout: 15000 })

  // 1. 平台下拉应有 6 个选项
  await page.click('.input-row .el-select') // 平台下拉（图文 Tab 下唯一 select）
  await page.waitForTimeout(500)
  const options = await page.$$eval('.el-select-dropdown__item', (els) => els.map((e) => e.textContent.trim()))
  console.log('1.平台下拉选项:', JSON.stringify(options))

  // 2. 选 B站 → 模板下拉联动（只显示 B站 3 个模板）
  await page.click('.el-select-dropdown__item:has-text("B站")')
  await page.waitForTimeout(800)
  await page.click('.template-row .el-select')
  await page.waitForTimeout(600)
  const templateNames = await page.$$eval('.template-row .el-select-dropdown__item', (els) => els.map((e) => e.textContent.replace(/\s+/g, '').trim()))
  console.log('2.B站模板:', JSON.stringify(templateNames))

  // 3. 历史记录页平台筛选 6 个
  await page.click('body')
  await page.click('text=历史记录')
  await page.waitForURL('**/history', { timeout: 10000 })
  await page.waitForTimeout(500)
  await page.click('.panel-actions .el-select, .filter-bar .el-select, .el-card .el-select')
  await page.waitForTimeout(500)
  const historyOptions = await page.$$eval('.el-select-dropdown__item:not(.selected)', (els) => els.map((e) => e.textContent.trim())).catch(() => [])
  console.log('3.历史记录筛选选项数:', historyOptions.length)

  await page.screenshot({ path: 'frontend/scripts/verify_new_platforms.png', fullPage: true })
  console.log('页面错误:', errors.length ? errors : '无')
  await browser.close()
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1) })
