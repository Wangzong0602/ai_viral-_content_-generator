// 用真实登录表单验证权限显示
const { chromium } = require('playwright')

;(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  // ---------- 场景1：普通用户登录 ----------
  const http = require('http')
  const post = (path, body) =>
    new Promise((res, rej) => {
      const data = JSON.stringify(body)
      const r = http.request(
        {
          hostname: '127.0.0.1',
          port: 8001,
          path,
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Content-Length': data.length },
        },
        (resp) => {
          let d = ''
          resp.on('data', (c) => (d += c))
          resp.on('end', () => res(JSON.parse(d)))
        }
      )
      r.on('error', rej)
      r.write(data)
      r.end()
    })

  const reg = await post('/api/v1/auth/register', {
    phone: '199' + String(Date.now() % 100000000).padStart(8, '0'),
    password: 'test123456',
  })
  const userPhone = reg.user.phone

  // 真实登录表单
  await page.goto('http://127.0.0.1:8002/login', { waitUntil: 'networkidle' })
  await page.getByPlaceholder('手机号或邮箱').fill(userPhone)
  await page.getByPlaceholder('密码').fill('test123456')
  await page.locator('button:has-text("登 录")').click()
  await page.waitForURL('**/')
  await page.waitForTimeout(2000)

  const nav1 = await page.locator('.nav-menu').textContent().catch(() => 'N/A')
  console.log('普通用户导航:', nav1.trim().replace(/\s+/g, ' '))
  console.log('  含后台管理:', nav1.includes('后台管理'), '(预期 false) ✅')

  // 退出
  await page.evaluate(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  })

  // ---------- 场景2：管理员登录 ----------
  await page.goto('http://127.0.0.1:8002/login', { waitUntil: 'networkidle' })
  await page.getByPlaceholder('手机号或邮箱').fill('19900000001')
  await page.getByPlaceholder('密码').fill('admin123456')
  await page.locator('button:has-text("登 录")').click()
  await page.waitForURL('**/')
  await page.waitForTimeout(2000)

  const nav2 = await page.locator('.nav-menu').textContent().catch(() => 'N/A')
  console.log('管理员导航:', nav2.trim().replace(/\s+/g, ' '))
  console.log('  含后台管理:', nav2.includes('后台管理'), '(预期 true) ✅')

  // 点击进入后台
  await page.locator('.nav-menu .el-menu-item:has-text("后台管理")').click()
  await page.waitForTimeout(2000)
  console.log('后台页 URL:', page.url())
  console.log('统计卡片:', await page.locator('.stat-card').count())

  await page.screenshot({ path: 'scripts/verify_admin_perm.png', fullPage: false })
  await browser.close()
})()
