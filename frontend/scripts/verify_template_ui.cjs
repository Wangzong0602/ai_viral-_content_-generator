// 验证内容模板前端交互：模板下拉联动 + 带模板生成选题
const { chromium } = require('playwright')

;(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  // API 注册
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
  await page.waitForTimeout(2000)

  // 1. 模板选择区可见
  const tplRow = await page.locator('.template-row').isVisible()
  console.log('模板选择区显示:', tplRow)

  // 2. 打开模板下拉（默认小红书 → 3 个模板）
  await page.locator('.template-row .el-select').click()
  await page.waitForTimeout(500)
  const tplCount = await page.locator('.el-select-dropdown__item').count()
  console.log('小红书模板数:', tplCount, '(预期3)')
  const tplNames = await page.locator('.el-select-dropdown__item span:first-child').allTextContents()
  console.log('模板名:', tplNames.join(' / '))

  // 3. 选择"痛点共鸣型"
  await page.locator('.el-select-dropdown__item:has-text("痛点共鸣型")').first().click()
  await page.waitForTimeout(500)
  const hint = await page.locator('.template-hint').textContent().catch(() => '')
  console.log('选中后提示:', hint.slice(0, 30))

  // 4. 切平台 → 模板联动（公众号 3 个不同模板）
  await page.locator('.input-row .el-select').first().click()
  await page.waitForTimeout(400)
  await page.locator('.el-select-dropdown__item:has-text("公众号")').first().click()
  await page.waitForTimeout(800)
  await page.locator('.template-row .el-select').click()
  await page.waitForTimeout(500)
  const tplCount2 = await page.locator('.el-select-dropdown__item').count()
  const tplNames2 = await page.locator('.el-select-dropdown__item span:first-child').allTextContents()
  console.log('切到公众号后模板数:', tplCount2, '| 模板:', tplNames2.join('/'))
  // 清空选择（点击空白关闭）
  await page.keyboard.press('Escape')

  // 5. 带模板生成选题
  await page.locator('.input-row .el-select').first().click()
  await page.waitForTimeout(400)
  await page.locator('.el-select-dropdown__item:has-text("小红书")').first().click()
  await page.waitForTimeout(800)
  await page.getByPlaceholder(/输入创作主题或关键词/).fill('健康养生')
  await page.locator('button:has-text("一键生成")').first().click()
  await page.waitForSelector('.topic-item', { timeout: 90000 })
  const topics = await page.locator('.topic-item').count()
  console.log('带模板生成选题:', topics, '(预期5)')

  await page.screenshot({ path: 'scripts/verify_template.png', fullPage: false })
  await browser.close()
})()
