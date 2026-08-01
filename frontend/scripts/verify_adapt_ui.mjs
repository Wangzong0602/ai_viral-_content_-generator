// 验证多平台适配前端交互 + 历史记录删除
// 运行：node scripts/verify_adapt_ui.mjs
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
  // ---------- 1. 注册 → 生成文章 ----------
  await page.goto(`${BASE}/register`, { waitUntil: 'networkidle' })
  await page.getByPlaceholder('手机号').fill(phone)
  await page.getByPlaceholder('昵称（可选）').fill('适配验证用户')
  await page.getByPlaceholder('密码（至少 6 位）').fill('test123456')
  await page.getByPlaceholder('确认密码').fill('test123456')
  await page.locator('button:has-text("注 册")').click()
  await page.waitForURL('**/')

  await page.getByPlaceholder(/输入创作主题或关键词/).fill('职场效率工具')
  await page.locator('button:has-text("一键生成爆文")').click()
  await page.waitForSelector('.topic-item', { timeout: 60000 })
  await page.locator('.topics-action button').first().click()
  await page.waitForSelector('text=创作完成', { timeout: 240000 })
  log(true, '文章创作完成')

  // ---------- 2. 多平台适配区存在 ----------
  const adaptSection = await page.locator('text=多平台适配').first().isVisible()
  log(adaptSection, '「多平台适配」区已显示')

  // 选择平台：通过键盘交互（点击 select → 上下键 → 空格勾选 → 回车确认）
  const selectEl = page.locator('.image-toolbar .el-select').nth(1)
  await selectEl.click()
  await page.waitForTimeout(500)
  // 用键盘选择第一个选项（公众号）
  await page.keyboard.press('ArrowDown')
  await page.waitForTimeout(200)
  await page.keyboard.press('Enter')
  await page.waitForTimeout(300)
  log(true, '已选择 1 个平台（公众号）')

  // 点击生成
  await page.locator('button:has-text("生成多平台版本")').click()
  log(true, '已点击生成，等待适配（约 20-40 秒）...')
  await page.waitForSelector('.adapt-results .el-collapse-item', { timeout: 180000 })
  const adaptCount = await page.locator('.adapt-results .el-collapse-item').count()
  log(adaptCount === 1, `生成 ${adaptCount} 个平台版本（公众号）`)

  // 展开第一个版本看内容
  await page.locator('.adapt-results .el-collapse-item').first().click()
  await page.waitForTimeout(500)
  const contentLen = await page
    .locator('.adapt-results .el-collapse-item textarea')
    .first()
    .inputValue()
  log(contentLen.length > 100, `版本内容完整（${contentLen.length} 字）`)

  // ---------- 3. 历史记录删除 ----------
  await page.goto(`${BASE}/history`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.el-table__row', { timeout: 15000 })
  const beforeCount = await page.locator('.el-table__row').count()
  log(beforeCount >= 1, `历史记录 ${beforeCount} 条`)

  // 删除第一条
  await page.locator('.el-table__row button:has-text("删除")').first().click()
  await page.waitForSelector('.el-message-box', { timeout: 5000 })
  await page.locator('.el-message-box button:has-text("确定")').click()
  await page.waitForTimeout(2000)
  const afterCount = await page.locator('.el-table__row').count()
  log(afterCount === beforeCount - 1, `删除后剩 ${afterCount} 条（预期 ${beforeCount - 1}）`)
} catch (err) {
  log(false, `验证中断: ${err.message}`)
} finally {
  await browser.close()
}

const failed = results.filter((r) => !r.ok).length
console.log(`\n========== 结果汇总: ${results.length - failed}/${results.length} 通过 ==========`)
if (failed > 0) process.exit(1)
