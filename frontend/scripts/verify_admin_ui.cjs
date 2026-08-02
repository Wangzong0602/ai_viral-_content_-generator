// 验证后台管理页（管理员登录 → 统计/用户/内容）
const { chromium } = require('playwright')

;(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  // 管理员登录（之前测试脚本创建了 19900000001/admin123456）
  const http = require('http')
  const post = (path, body) =>
    new Promise((resolve, reject) => {
      const data = JSON.stringify(body)
      const req = http.request(
        {
          hostname: '127.0.0.1',
          port: 8001,
          path,
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Content-Length': data.length },
        },
        (res) => {
          let d = ''
          res.on('data', (c) => (d += c))
          res.on('end', () => resolve(JSON.parse(d)))
        }
      )
      req.on('error', reject)
      req.write(data)
      req.end()
    })

  let login
  try {
    login = await post('/api/v1/auth/login', { account: '19900000001', password: 'admin123456' })
  } catch (e) {
    console.log('❌ 管理员登录失败（可能测试数据被清理）')
    await browser.close()
    return
  }

  await page.goto('http://127.0.0.1:8002/login', { waitUntil: 'networkidle' })
  await page.evaluate(
    (t) => {
      localStorage.setItem('token', t)
      localStorage.setItem('user', JSON.stringify({ nickname: '系统管理员' }))
    },
    login.access_token
  )
  await page.goto('http://127.0.0.1:8002/admin', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(2000)

  console.log('URL:', page.url())
  console.log('左侧菜单项:', await page.locator('.admin-menu-item').count(), '(预期3)')
  console.log('统计卡片:', await page.locator('.stat-card').count(), '(预期4)')

  // 用户管理
  await page.locator('.admin-menu-item:has-text("用户管理")').click()
  await page.waitForTimeout(1500)
  console.log('用户表格行数:', await page.locator('.el-table__row').count())

  // 内容管理
  await page.locator('.admin-menu-item:has-text("内容管理")').click()
  await page.waitForTimeout(1500)
  console.log('内容表格行数:', await page.locator('.el-table__row').count())

  await page.screenshot({ path: 'scripts/verify_admin_ui.png', fullPage: false })
  await browser.close()
})()
