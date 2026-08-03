// 回归验证：5 个页面的导航（会员中心入口 + `n bug 修复）无异常
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

  const pages = [
    { path: '/', name: '创作工作台' },
    { path: '/batch', name: '批量生成' },
    { path: '/dashboard', name: '数据看板' },
    { path: '/history', name: '历史记录' },
    { path: '/admin', name: '后台管理' },
  ]
  for (const p of pages) {
    await page.goto(`${BASE}${p.path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(800)
    // 检查导航栏：会员中心入口存在、无 `n 乱码
    const navText = await page.textContent('.nav-menu')
    const hasMember = navText.includes('会员中心')
    const hasN = navText.includes('\`n')
    console.log(`${p.name}: 会员中心入口=${hasMember} ` + (hasN ? '❌ 仍有`n乱码!' : '✓ 无乱码'))
    if (hasN) errors.push(`${p.name} nav 有 \`n 乱码`)
  }

  // 验证用户下拉菜单有会员中心
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' })
  await page.hover('.user-info')
  await page.waitForTimeout(500)
  const dropdownText = await page.textContent('.el-dropdown-menu')
  console.log('用户下拉含会员中心:', dropdownText.includes('会员中心'))

  await browser.close()
  console.log('错误:', errors.length ? errors : '无')
  process.exit(errors.length ? 1 : 0)
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1) })
