// 验证修复：敏感关键词一键生成不再超时失败
const { chromium } = require('playwright')

;(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text())
  })

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

  // 敏感关键词（触发联网搜索，之前会超时）
  console.log('输入敏感关键词...')
  await page.getByPlaceholder(/输入创作主题或关键词/).fill('中国人首获菲尔兹奖')
  const start = Date.now()
  await page.locator('button:has-text("一键生成")').first().click()

  try {
    await page.waitForSelector('.topic-item', { timeout: 150000 })
    console.log(`✅ 选题生成成功！耗时 ${(Date.now() - start) / 1000}s`)
    console.log('选题数:', await page.locator('.topic-item').count())
  } catch (e) {
    console.log('❌ 选题超时/失败:', e.message.slice(0, 200))
  }

  // 检查错误提示
  const errMsgs = errors.filter((m) => !m.includes('favicon'))
  console.log('页面错误:', errMsgs.length ? errMsgs.slice(0, 3) : '无')

  await browser.close()
})()
