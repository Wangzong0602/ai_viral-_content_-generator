// SEO 智能体前端验证：结果区显示关键词/话题标签/优化标题
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

  // 图文生成（真调 AI，约 2-4 分钟）
  await page.fill('.input-card .el-input__inner', '跑步新手入门')
  await page.click('button:has-text("一键生成爆文")')
  await page.waitForSelector('.topics-section', { timeout: 180000 })
  await page.click('button:has-text("开始创作")')
  await page.waitForSelector('.result-card:visible', { timeout: 420000 })
  await page.waitForTimeout(1000)

  // 验证 SEO 报告区
  const seoText = await page.textContent('.seo-report').catch(() => '')
  console.log('SEO 报告区显示:', seoText.includes('优化标题') && seoText.includes('关键词'))
  const kwCount = await page.$$eval('.seo-report .seo-tag', (els) => els.length)
  console.log('关键词+标签标签数:', kwCount)
  const hasMeta = await page.textContent('.seo-report').then((t) => t.includes('搜索描述'))
  console.log('含搜索描述:', hasMeta)
  await page.screenshot({ path: 'frontend/scripts/verify_seo_agent.png', fullPage: true })

  console.log('页面错误:', errors.length ? errors : '无')
  await browser.close()
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1) })
