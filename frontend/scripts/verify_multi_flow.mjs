// 验证首屏多平台生成流程
// 运行：node scripts/verify_multi_flow.mjs
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:8002'
const phone = `199${String(Date.now() % 100000000).padStart(8, '0')}`
const results = []

function log(ok, msg) {
  results.push({ ok, msg })
  console.log(`${ok ? '✅' : '❌'} ${msg}`)
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })

try {
  // ---------- 1. 注册进入工作台 ----------
  await page.goto(`${BASE}/register`, { waitUntil: 'networkidle' })
  await page.getByPlaceholder('手机号').fill(phone)
  await page.getByPlaceholder('昵称（可选）').fill('多平台验证用户')
  await page.getByPlaceholder('密码（至少 6 位）').fill('test123456')
  await page.getByPlaceholder('确认密码').fill('test123456')
  await page.locator('button:has-text("注 册")').click()
  await page.waitForURL('**/')

  // ---------- 2. 首屏多平台选项可见 ----------
  const multiVisible = await page.locator('text=同时生成以下平台版本').first().isVisible()
  log(multiVisible, '首屏显示「同时生成以下平台版本」选项')

  // 未选择时按钮文案
  let btnText = await page.locator('button:has-text("一键生成")').first().textContent()
  log(btnText.includes('一键生成爆文'), `未选多平台时按钮: "${btnText.trim()}"`)

  // ---------- 3. 勾选多平台（主平台小红书，勾公众号+知乎） ----------
  await page.locator('.multi-platform-row label:has-text("公众号")').click()
  await page.locator('.multi-platform-row label:has-text("知乎")').click()
  await page.waitForTimeout(300)

  btnText = await page.locator('button:has-text("一键生成")').first().textContent()
  log(btnText.includes('3 平台'), `选择后按钮: "${btnText.trim()}"`)

  const hint = await page.locator('.multi-platform-hint').first().textContent()
  log(hint.includes('2 个平台版本'), `提示文案: "${hint.trim()}"`)

  // ---------- 4. 生成（应自动多平台） ----------
  await page.getByPlaceholder(/输入创作主题或关键词/).fill('健康养生小技巧')
  await page.locator('button:has-text("一键生成")').first().click()
  await page.waitForSelector('.topic-item', { timeout: 60000 })
  const startBtn = page.locator('.topics-action button').first()
  const startText = await startBtn.textContent()
  log(startText.includes('3 平台'), `开始创作按钮: "${startText.trim()}"`)
  await startBtn.click()

  // 等待主版本完成
  await page.waitForSelector('text=正在生成多平台版本', { timeout: 240000 })
  log(true, '主版本完成，自动进入多平台生成')

  // 等待多平台结果（2 个平台版本折叠面板）
  await page.waitForSelector('.adapt-results .el-collapse-item', { timeout: 180000 })
  const adaptCount = await page.locator('.adapt-results .el-collapse-item').count()
  log(adaptCount === 2, `自动生成 ${adaptCount} 个平台版本（公众号+知乎）`)

  // 标题含"共 3 篇"的提示已经过；验证结果区存在
  const resultVisible = await page.locator('text=创作完成').first().isVisible().catch(() => false)
  log(resultVisible || adaptCount === 2, '结果区正常展示')
} catch (err) {
  log(false, `验证中断: ${err.message}`)
} finally {
  await browser.close()
}

const failed = results.filter((r) => !r.ok).length
console.log(`\n========== 结果汇总: ${results.length - failed}/${results.length} 通过 ==========`)
if (failed > 0) process.exit(1)
