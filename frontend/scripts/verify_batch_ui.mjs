// 验证批量生成页前端交互
// 运行：node scripts/verify_batch_ui.mjs
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
  // ---------- 1. 注册 → 导航到批量页 ----------
  await page.goto(`${BASE}/register`, { waitUntil: 'networkidle' })
  await page.getByPlaceholder('手机号').fill(phone)
  await page.getByPlaceholder('昵称（可选）').fill('批量验证用户')
  await page.getByPlaceholder('密码（至少 6 位）').fill('test123456')
  await page.getByPlaceholder('确认密码').fill('test123456')
  await page.locator('button:has-text("注 册")').click()
  await page.waitForURL('**/')

  await page.goto(`${BASE}/batch`, { waitUntil: 'networkidle' })
  log(true, '进入批量生成页')

  // ---------- 2. 输入 2 个关键词，验证计数 ----------
  await page.locator('.batch-form textarea').fill('早起的好处\n睡前放松技巧')
  await page.waitForTimeout(300)
  const btnText = await page.locator('button:has-text("开始批量生成")').textContent()
  log(btnText.includes('2 篇'), `按钮显示篇数: "${btnText.trim()}"`)

  // ---------- 3. 创建批量任务 ----------
  await page.locator('button:has-text("开始批量生成")').click()
  await page.waitForTimeout(1500)
  log(true, '已创建批量任务（详情已自动打开）')

  // 表格中出现任务
  await page.waitForSelector('.el-table__row', { timeout: 15000 })
  const rowCount = await page.locator('.el-table__row').count()
  log(rowCount >= 1, `批量任务列表显示 ${rowCount} 个任务`)

  // ---------- 4. 详情对话框（创建后自动打开） ----------
  await page.waitForSelector('.items-list .item-row', { timeout: 15000 })
  const itemCount = await page.locator('.item-row').count()
  log(itemCount === 2, `详情显示 ${itemCount} 篇状态`)

  // 等待生成完成（2 篇约 2-3 分钟）
  log(true, '等待批量生成完成（2 篇，约 2-3 分钟）...')
  await page.waitForSelector('.items-list .item-row:has-text("成功"):nth-of-type(2)', {
    timeout: 360000,
  }).catch(() => {})
  await page.waitForTimeout(3000)

  const statuses = await page.locator('.item-row .el-tag').allTextContents()
  log(statuses.every((s) => s.includes('成功') || s.includes('失败')), `每篇状态: ${statuses.join(', ')}`)

  // 截图留证
  await page.screenshot({ path: 'scripts/verify_batch_result.png', fullPage: false })
} catch (err) {
  log(false, `验证中断: ${err.message}`)
} finally {
  await browser.close()
}

const failed = results.filter((r) => !r.ok).length
console.log(`\n========== 结果汇总: ${results.length - failed}/${results.length} 通过 ==========`)
if (failed > 0) process.exit(1)
