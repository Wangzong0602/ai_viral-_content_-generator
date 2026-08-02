// 浏览器验证：完整创作后事实核查警告条展示
const { chromium } = require('playwright')

;(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

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

  const reg = await post('/api/v1/auth/register', {
    phone: '199' + String(Date.now() % 100000000).padStart(8, '0'),
    password: 'test123456',
  })

  await page.goto('http://127.0.0.1:8002/login', { waitUntil: 'networkidle' })
  await page.evaluate(
    (t) => {
      localStorage.setItem('token', t)
      localStorage.setItem('user', JSON.stringify({ nickname: 'x' }))
    },
    reg.access_token
  )
  await page.goto('http://127.0.0.1:8002/', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1500)

  // 输入事实敏感关键词
  await page.getByPlaceholder(/输入创作主题或关键词/).fill('中国人首获菲尔兹奖 王虹邓煜')
  await page.locator('button:has-text("一键生成")').first().click()

  // 等待选题
  await page.waitForSelector('.topic-item', { timeout: 120000 })
  console.log('选题生成 OK')
  await page.locator('.topics-action button').first().click()

  // 等待创作完成（含搜索+事实核查，可能 3-5 分钟）
  console.log('等待创作完成（含联网搜索+事实核查）...')
  await page.waitForSelector('text=创作完成', { timeout: 420000 })

  // 检查事实核查警告条
  await page.waitForTimeout(1000)
  const factCheckVisible = await page.locator('.fact-check').isVisible().catch(() => false)
  console.log('事实核查警告条显示:', factCheckVisible)

  if (factCheckVisible) {
    const riskClass = await page.locator('.fact-check').getAttribute('class')
    console.log('风险等级 class:', riskClass)
    const warning = await page.locator('.fact-warning').textContent()
    console.log('警告文案:', warning.trim().slice(0, 80))
  }

  await page.screenshot({ path: 'scripts/verify_factcheck_ui.png', fullPage: false })
  await browser.close()
})()
