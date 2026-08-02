// 验证数据看板页面（用已造好的测试用户登录）
const { chromium } = require('playwright')

;(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  // 用 HTTP 登录拿 token（手机号从 seed 脚本输出，这里直接从数据库最新 199 用户取）
  const http = require('http')
  const get = (path) =>
    new Promise((resolve, reject) => {
      http
        .get({ hostname: '127.0.0.1', port: 8001, path }, (res) => {
          let d = ''
          res.on('data', (c) => (d += c))
          res.on('end', () => resolve(JSON.parse(d)))
        })
        .on('error', reject)
    })

  // 注册一个新用户并造数据（简单起见：直接用注册+造数据脚本已建的，用登录接口）
  // 这里重新注册（会多一个用户，但可接受）
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

  const phone = '199' + String(Date.now() % 100000000).padStart(8, '0')
  const reg = await post('/api/v1/auth/register', { phone, password: 'test123456' })

  // 为该用户造 3 篇数据
  const { execSync } = require('child_process')
  execSync(
    `"E:\\miniconda3\\envs\\fastapi_env\\python.exe" -c "import pymysql; conn=pymysql.connect(host='127.0.0.1',port=3306,user='root',password='010819',database='ai_content_generator',charset='utf8mb4'); cur=conn.cursor(); [(cur.execute('INSERT INTO creation_tasks (user_id,keyword,platform,selected_title,status,current_step,content,sensitive_report,quality_score,error_message,created_at,completed_at) VALUES (%s,%s,%s,%s,2,\\'done\\',%s,\\'{}\\',%s,\\'\\',NOW(),NOW())', (${
      reg.user.id
    }, f'看板{i}', p, f'标题{i}', '正文内容' * 50, s))) for i,(p,s) in enumerate([('小红书',95),('公众号',88),('知乎',92)])]; conn.commit(); conn.close()"`,
    { encoding: 'utf-8' }
  )

  await page.goto('http://127.0.0.1:8002/login', { waitUntil: 'networkidle' })
  await page.evaluate(
    (t) => {
      localStorage.setItem('token', t)
      localStorage.setItem('user', JSON.stringify({ nickname: '看板' }))
    },
    reg.access_token
  )
  await page.goto('http://127.0.0.1:8002/dashboard', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(3000)

  console.log('概览卡片数:', await page.locator('.summary-card').count(), '(预期4)')
  const values = await page.locator('.summary-value').allTextContents()
  console.log('概览数值:', values.join(' | '))
  console.log('总创作=3:', values[0] === '3')
  console.log('节省时间=6:', values[2] === '6')

  const charts = await page.locator('.chart canvas').count()
  console.log('ECharts canvas:', charts, '(预期3)')

  const nav = await page.locator('.nav-menu').textContent()
  console.log('导航含数据看板:', nav.includes('数据看板'))

  await page.screenshot({ path: 'scripts/verify_dashboard.png', fullPage: false })
  await browser.close()
})()
