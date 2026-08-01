// 验证爆文逆向分析前端交互
// 运行：node scripts/verify_analyze_ui.mjs
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:8002'
const phone = `199${String(Date.now() % 100000000).padStart(8, '0')}`
const results = []

function log(ok, msg) {
  results.push({ ok, msg })
  console.log(`${ok ? '✅' : '❌'} ${msg}`)
}

const SAMPLE_ARTICLE = `
为什么你写的文章没人看？我研究了100篇10万+爆文，发现一个惊人的规律。
大家好，我是小明。去年我写了200篇文章，平均阅读量只有500。
直到我花了三个月拆解了100篇爆文，终于找到了爆款的底层逻辑。
第一，标题必须有数字。比如'5个方法''3个坑''100天'，数字能让读者预判价值。
第二，开头三秒必须戳痛点。'你是不是也这样？'比'大家好'有效十倍。
第三，内容要有情绪曲线。先共鸣，再焦虑，给方案，最后爽点。
第四，结尾一定要引导。'收藏起来慢慢看''评论区告诉我你的故事'。
第五，关键词要自然融入，让平台算法能看懂。
我把拆解笔记整理成了文档，需要的朋友评论区扣1。
关注我，下期拆解更多爆款案例。
`

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })

try {
  // ---------- 1. 注册进入工作台 ----------
  await page.goto(`${BASE}/register`, { waitUntil: 'networkidle' })
  await page.getByPlaceholder('手机号').fill(phone)
  await page.getByPlaceholder('昵称（可选）').fill('分析验证用户')
  await page.getByPlaceholder('密码（至少 6 位）').fill('test123456')
  await page.getByPlaceholder('确认密码').fill('test123456')
  await page.locator('button:has-text("注 册")').click()
  await page.waitForURL('**/')
  log(true, '注册成功进入工作台')

  // ---------- 2. 逆向分析区存在 ----------
  const sectionVisible = await page.locator('text=爆文逆向分析').first().isVisible()
  log(sectionVisible, '「爆文逆向分析」区已显示')

  // ---------- 3. 粘贴内容 → 分析 ----------
  await page.locator('.analyze-input textarea').fill(SAMPLE_ARTICLE.trim())
  await page.locator('button:has-text("开始分析")').click()
  log(true, '已点击开始分析，等待结果（约 10-30 秒）...')

  await page.waitForSelector('.analyze-result', { timeout: 120000 })
  log(true, '分析结果已展示')

  // 验证 7 个报告项
  const reportItems = await page.locator('.report-item').count()
  log(reportItems === 7, `报告包含 ${reportItems} 个要素卡片`)

  const labels = await page.locator('.report-label').allTextContents()
  const hasAll = ['标题钩子', '开头', '内容结构', '情绪价值', '行动召唤', 'SEO', '方法论'].every((k) =>
    labels.some((l) => l.includes(k))
  )
  log(hasAll, '7 个要素标签齐全')

  const firstReport = await page.locator('.report-text').first().textContent()
  log(firstReport.length > 20, `报告内容非空（${firstReport.length} 字）`)

  // 截图留证
  await page.screenshot({ path: 'scripts/verify_analyze_result.png', fullPage: false })
} catch (err) {
  log(false, `验证中断: ${err.message}`)
} finally {
  await browser.close()
}

const failed = results.filter((r) => !r.ok).length
console.log(`\n========== 结果汇总: ${results.length - failed}/${results.length} 通过 ==========`)
if (failed > 0) process.exit(1)
