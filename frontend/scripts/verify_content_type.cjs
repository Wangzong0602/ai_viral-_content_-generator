// 多内容形态前端实测：形态选择器 → 视频脚本选题 → 生成 → 结果标签 → 历史记录标签
const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8002'

async function main() {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))

  // 登录管理员（企业版，不限配额）
  await page.goto(`${BASE}/login`)
  await page.fill('input[placeholder*="手机号"]', '19900000001')
  await page.fill('input[placeholder*="密码"]', 'admin123456')
  await page.click('button[type="submit"], .submit-btn, button:has-text("登 录"), button:has-text("登录")')
  await page.waitForURL('**/', { timeout: 15000 })

  // 1. 形态选择器存在，默认图文
  const typeSelect = await page.textContent('.input-row .el-select')
  console.log('1.形态选择器存在:', !!typeSelect)

  // 2. 切换为视频脚本 → 提示文案出现 + 多平台/模板隐藏
  await page.locator('.input-row .el-select').first().click()
  await page.waitForTimeout(400)
  await page.click('.el-select-dropdown__item:has-text("视频脚本")')
  await page.waitForTimeout(400)
  const hint = await page.textContent('.content-type-hint')
  const multiVisible = await page.$('.multi-platform-row')
  const templateVisible = await page.$('.template-row')
  console.log('2.形态提示:', hint.trim().slice(0, 30))
  console.log('   多平台已隐藏:', !multiVisible, '| 模板已隐藏:', !templateVisible)

  // 3. 生成视频脚本选题（真调 AI，约 30-60 秒）
  await page.fill('.input-card input[placeholder*="主题"]', '早起习惯养成')
  await page.click('button:has-text("一键生成视频脚本")')
  await page.waitForSelector('.topics-section', { timeout: 180000 })
  const topicCount = await page.$$('.topic-item, .topic-list > div, .topic-card').then((els) => els.length)
  const topicsText = await page.textContent('.topics-section')
  console.log('3.视频脚本选题已生成:', topicsText.includes('爆款选题'))

  // 4. 开始创作 → 等待完成
  await page.click('button:has-text("开始创作")')
  await page.waitForSelector('.result-card', { timeout: 300000 })
  await page.waitForTimeout(1000)

  // 5. 结果区：形态标签 + 内容含结构标记
  const resultHeader = await page.textContent('.result-card .result-header')
  const contentText = await page.inputValue('.result-editor textarea')
  console.log('5.结果区形态标签:', resultHeader.includes('视频脚本'))
  console.log('   内容含【开场】结构:', contentText.includes('【开场') || contentText.includes('开场'))
  await page.screenshot({ path: 'frontend/scripts/verify_content_type.png', fullPage: true })

  // 6. 历史记录形态标签
  await page.click('text=历史记录')
  await page.waitForURL('**/history', { timeout: 10000 })
  await page.waitForSelector('.el-table__row', { timeout: 10000 })
  const firstRow = await page.locator('.el-table__row').first().textContent()
  console.log('6.历史记录形态标签:', firstRow.includes('视频脚本'))
  await page.screenshot({ path: 'frontend/scripts/verify_history_content_type.png', fullPage: true })

  console.log('页面错误:', errors.length ? errors : '无')
  await browser.close()
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1) })
