// Tab 化验证：图文 Tab 有平台选择器，形态 Tab 无平台选择器 + 电商生成内容纯净性
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

  // 1. 默认图文 Tab：平台选择器可见 + 模板可见 + 多平台可见
  const platformSel = await page.$('.input-row .el-select')
  const templateRow = await page.$('.template-row')
  const multiRow = await page.$('.multi-platform-row')
  console.log('1.图文 Tab: 平台选择器=', !!platformSel, '模板=', !!templateRow, '多平台=', !!multiRow)

  // 2. 切到视频脚本 Tab：平台/模板/多平台全隐藏，提示出现
  await page.click('.type-tabs .el-radio-button:has-text("视频脚本")')
  await page.waitForTimeout(400)
  console.log('2.视频脚本 Tab: 平台选择器=', !!(await page.$('.input-row .el-select')), '模板=', !!(await page.$('.template-row')), '多平台=', !!(await page.$('.multi-platform-row')))
  console.log('   提示:', (await page.textContent('.content-type-hint')).trim().slice(0, 30))
  console.log('   占位符:', await page.getAttribute('.input-card .el-input__inner', 'placeholder'))

  // 3. 电商带货完整生成（验证输出为纯电商文案，无平台污染）
  await page.click('.type-tabs .el-radio-button:has-text("电商带货")')
  await page.waitForTimeout(400)
  await page.fill('.input-card .el-input__inner', '无线蓝牙耳机')
  await page.click('button:has-text("一键生成电商带货")')
  await page.waitForSelector('.topics-section', { timeout: 180000 })
  console.log('3.电商选题生成 ✓')

  await page.click('button:has-text("开始创作")')
  await page.waitForSelector('.result-card', { timeout: 300000 })
  await page.waitForTimeout(1000)
  const content = await page.inputValue('.result-editor textarea')
  console.log('4.电商文案长度:', content.length)
  console.log('   含卖点/痛点结构:', /【[^】]*(卖点|痛点|信任|价格|行动)[^】]*】/.test(content) || content.includes('卖点') || content.includes('痛点'))
  console.log('   无平台污染(不含小红书机制描述):', !content.includes('小红书的推荐机制') && !content.includes('高完播率'))
  console.log('   内容前 150 字:', content.replace(/\s+/g, ' ').slice(0, 150))
  await page.screenshot({ path: 'frontend/scripts/verify_type_tabs.png', fullPage: true })

  console.log('页面错误:', errors.length ? errors : '无')
  await browser.close()
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1) })
