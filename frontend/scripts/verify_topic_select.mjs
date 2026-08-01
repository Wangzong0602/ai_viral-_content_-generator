// 验证选题选择（两步分离）交互
// 运行：node scripts/verify_topic_select.mjs
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
  await page.getByPlaceholder('昵称（可选）').fill('选题验证用户')
  await page.getByPlaceholder('密码（至少 6 位）').fill('test123456')
  await page.getByPlaceholder('确认密码').fill('test123456')
  await page.locator('button:has-text("注 册")').click()
  await page.waitForURL('**/')
  log(true, '注册成功并进入工作台')

  // ---------- 2. 输入关键词生成选题 ----------
  await page.getByPlaceholder(/输入创作主题或关键词/).fill('健康养生')
  await page.locator('button:has-text("一键生成爆文")').click()

  // 等待选题出现（不自动创作）
  await page.waitForSelector('.topic-item', { timeout: 60000 })
  const topicCount = await page.locator('.topic-item').count()
  log(topicCount === 5, `生成 ${topicCount} 个选题`)

  // 关键验证：此时【不】应该出现"生成进度"卡片（未自动创作）
  const genVisible = await page.locator('.gen-card').isVisible().catch(() => false)
  log(!genVisible, '生成选题后停留，未自动开始创作')

  // ---------- 3. 点击选择第 3 个选题 ----------
  await page.locator('.topic-item').nth(2).click()
  const activeIdx = await page
    .locator('.topic-item')
    .nth(2)
    .evaluate((el) => el.classList.contains('topic-active'))
  log(activeIdx, '点击第 3 个选题后高亮选中')

  // 验证"开始创作"按钮文案包含所选标题
  const btnText = await page.locator('.topics-action button').first().textContent()
  log(btnText.includes('开始创作'), '出现"开始创作"按钮')

  // ---------- 4. 点击开始创作，等待完成 ----------
  await page.locator('.topics-action button').first().click()
  log(true, '已点击开始创作，等待生成完成（约 2 分钟）...')
  await page.waitForSelector('text=创作完成', { timeout: 240000 })
  log(true, '文章创作完成（使用的是所选选题）')

  // 验证导出的标题确实是第 3 个选题（编辑器上方应有该标题）
  // （标题在 result 头部没有直接显示，验证 selectedTopic 生效即可，
  //   通过历史记录接口确认）
  const resp = await page.request.get(`${BASE}/api/v1/content/tasks`, {
    headers: { Authorization: `Bearer ${await page.evaluate(() => localStorage.getItem('token'))}` },
  })
  const tasks = await resp.json()
  const latest = tasks[0]
  const thirdTitle = await page.locator('.topic-item').nth(2).locator('.topic-title').textContent()
  log(latest.selected_title === thirdTitle.trim(), '后端记录确认使用了所选第 3 个选题')
} catch (err) {
  log(false, `验证中断: ${err.message}`)
} finally {
  await browser.close()
}

const failed = results.filter((r) => !r.ok).length
console.log(`\n========== 结果汇总: ${results.length - failed}/${results.length} 通过 ==========`)
if (failed > 0) process.exit(1)
