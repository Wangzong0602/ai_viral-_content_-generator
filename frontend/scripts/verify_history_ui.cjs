// 验证历史记录增强前端交互（用已造数据的账号登录）
const { chromium } = require('playwright')

;(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  // 从数据库取最新 199 用户的手机号登录（造数据脚本创建的）
  const { execSync } = require('child_process')
  const phone = execSync(
    `"E:\\miniconda3\\envs\\fastapi_env\\python.exe" -c "import pymysql; conn=pymysql.connect(host='127.0.0.1',port=3306,user='root',password='010819',database='ai_content_generator',charset='utf8mb4'); cur=conn.cursor(); cur.execute('SELECT phone FROM users ORDER BY id DESC LIMIT 1'); print(cur.fetchone()[0]); conn.close()"`,
    { encoding: 'utf-8' }
  ).trim()
  console.log('登录手机号:', phone)

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

  const login = await post('/api/v1/auth/login', { account: phone, password: 'test123456' })

  await page.goto('http://127.0.0.1:8002/login', { waitUntil: 'networkidle' })
  await page.evaluate(
    (t) => {
      localStorage.setItem('token', t)
      localStorage.setItem('user', JSON.stringify({ nickname: 'x' }))
    },
    login.access_token
  )
  await page.goto('http://127.0.0.1:8002/history', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(2500)

  console.log('表格行数:', await page.locator('.el-table__row').count(), '(预期4)')

  const starred = await page.locator('.el-table__row button.is-warning').count()
  console.log('已收藏星标:', starred, '(预期2)')

  // 平台筛选
  await page.locator('.filter-toolbar .el-select').click()
  await page.waitForTimeout(400)
  await page.locator('.el-select-dropdown__item:has-text("小红书")').first().click()
  await page.waitForTimeout(1500)
  console.log('小红书筛选行数:', await page.locator('.el-table__row').count(), '(预期2)')

  await page.locator('.filter-toolbar button:has-text("清除筛选")').click()
  await page.waitForTimeout(1000)
  console.log('清除后行数:', await page.locator('.el-table__row').count(), '(预期4)')

  // 搜索
  await page.locator('.filter-toolbar input').first().fill('效率')
  await page.waitForTimeout(1200)
  console.log('搜索"效率"行数:', await page.locator('.el-table__row').count(), '(预期2)')

  // 只看收藏
  await page.locator('.filter-toolbar input').first().fill('')
  await page.waitForTimeout(800)
  await page.locator('.filter-toolbar .el-checkbox').click()
  await page.waitForTimeout(1200)
  console.log('只看收藏行数:', await page.locator('.el-table__row').count(), '(预期2)')

  // 点击星标取消收藏（局部更新）
  await page.locator('.el-table__row button.is-warning').first().click()
  await page.waitForTimeout(800)
  console.log('取消收藏后行数:', await page.locator('.el-table__row').count(), '(预期1)')

  await page.screenshot({ path: 'scripts/verify_history_enhance.png', fullPage: false })
  await browser.close()
})()
