// 验证导航栏批量生成入口
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
  await page.goto(`${BASE}/register`, { waitUntil: 'networkidle' })
  await page.getByPlaceholder('手机号').fill(phone)
  await page.getByPlaceholder('昵称（可选）').fill('导航验证')
  await page.getByPlaceholder('密码（至少 6 位）').fill('test123456')
  await page.getByPlaceholder('确认密码').fill('test123456')
  await page.locator('button:has-text("注 册")').click()
  await page.waitForURL('**/')

  // 检查导航栏
  const menuText = await page.locator('.nav-menu').textContent()
  log(menuText.includes('批量生成'), `工作台导航包含"批量生成": "${menuText.trim()}"`)

  // 点击批量生成菜单
  await page.locator('.nav-menu .el-menu-item:has-text("批量生成")').click()
  await page.waitForURL('**/batch')
  await page.waitForTimeout(1000)

  const hasForm = await page.locator('text=批量内容生成').first().isVisible()
  log(hasForm, '批量生成页正常打开（显示"批量内容生成"表单）')

  // 历史记录页导航也应有
  await page.goto(`${BASE}/history`, { waitUntil: 'networkidle' })
  const historyMenu = await page.locator('.nav-menu').textContent()
  log(historyMenu.includes('批量生成'), '历史记录页导航也包含"批量生成"')
} catch (err) {
  log(false, `验证中断: ${err.message}`)
} finally {
  await browser.close()
}

const failed = results.filter((r) => !r.ok).length
console.log(`\n========== 结果汇总: ${results.length - failed}/${results.length} 通过 ==========`)
if (failed > 0) process.exit(1)
