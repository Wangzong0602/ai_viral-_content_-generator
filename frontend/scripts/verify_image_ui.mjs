// AI 配图前端功能浏览器验证脚本
// 用 Playwright 无头浏览器走完整流程：注册 → 配图 UI 出现 → 生成配图 → 换一张
// 运行：node scripts/verify_image_ui.mjs
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
  // ---------- 1. 注册并进入工作台 ----------
  await page.goto(`${BASE}/register`, { waitUntil: 'networkidle' })
  await page.getByPlaceholder('手机号').fill(phone)
  await page.getByPlaceholder('昵称（可选）').fill('配图验证用户')
  await page.getByPlaceholder('密码（至少 6 位）').fill('test123456')
  await page.getByPlaceholder('确认密码').fill('test123456')
  await page.locator('button:has-text("注 册")').click()
  await page.waitForURL('**/')
  log(true, `注册成功并进入工作台 (${phone})`)

  // ---------- 2. 直接验证配图 UI（不跑完整创作，用历史记录的旧文章? 不可行）
  // 方案：用已有历史记录的文章内容——先检查历史记录页是否有可复用的文章
  // 更简单：直接构造一个"已有文章"的场景不可行，改为先跑一次短创作
  // 但完整创作约 2 分钟太长。改用：检查配图区在结果页正常渲染的代码路径
  // 这里通过先走一遍完整创作验证（预算 3 分钟）

  // 输入主题并生成
  await page.getByPlaceholder(/输入创作主题或关键词/).fill('效率工具推荐')
  await page.locator('button:has-text("一键生成爆文")').click()

  // 等待生成完成（SSE 全流程约 1.5-3 分钟）
  log(true, '已点击一键生成，等待创作完成（约 2 分钟）...')
  await page.waitForSelector('text=创作完成', { timeout: 240000 })
  log(true, '文章创作完成')

  // ---------- 3. 触发 AI 配图 ----------
  await page.locator('button:has-text("✨ 生成配图")').click()
  log(true, '已点击生成配图，等待图片生成（约 30-60 秒）...')

  // 等待图片出现（img 元素加载完成）
  await page.waitForSelector('.image-grid .el-image img', { timeout: 180000 })
  await page.waitForTimeout(3000) // 等图片渲染
  const imgCount = await page.locator('.image-grid .el-image img').count()
  log(imgCount >= 1, `配图生成并展示 ${imgCount} 张`)

  // 验证图片 URL 可加载（naturalWidth > 0 表示加载成功）
  const loaded = await page.locator('.image-grid .el-image img').evaluateAll(
    (imgs) => imgs.every((img) => img.naturalWidth > 0)
  )
  log(loaded, '图片真实加载成功（naturalWidth > 0）')

  // 截图留证
  await page.screenshot({ path: 'scripts/verify_image_result.png', fullPage: false })

  // ---------- 4. 单张重新生成 ----------
  await page.locator('.image-actions button:has-text("换一张")').first().click()
  log(true, '已点击"换一张"，等待重新生成（约 20-60 秒）...')
  await page.waitForTimeout(45000) // 等待重生成
  // 验证按钮不在 loading 状态（说明完成）
  const stillLoading = await page
    .locator('.image-actions button:has-text("换一张")')
    .first()
    .evaluate((btn) => btn.classList.contains('is-loading'))
  log(!stillLoading, '单张重新生成完成（按钮已恢复）')

  // ---------- 5. 验证 /images 代理（直接请求图片 URL） ----------
  const imgSrc = await page.locator('.image-grid .el-image img').first().getAttribute('src')
  if (imgSrc) {
    const resp = await page.request.get(`${BASE}${imgSrc.startsWith('/') ? imgSrc : '/' + imgSrc}`)
    const ct = resp.headers()['content-type'] || ''
    log(resp.status() === 200 && ct.startsWith('image/'), `/images 代理正常: ${resp.status()} ${ct}`)
  } else {
    log(false, '无法获取图片 src')
  }
} catch (err) {
  log(false, `验证中断: ${err.message}`)
} finally {
  await browser.close()
}

// 汇总
const failed = results.filter((r) => !r.ok).length
console.log(`\n========== 结果汇总: ${results.length - failed}/${results.length} 通过 ==========`)
if (failed > 0) process.exit(1)
