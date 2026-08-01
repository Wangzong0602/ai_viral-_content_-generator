// 验证导出功能：MD 带图片引用 + HTML 内嵌图片
// 运行：node scripts/verify_export.mjs
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:8002'
const phone = `199${String(Date.now() % 100000000).padStart(8, '0')}`
const results = []
const downloadDir = new URL('.', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1') + 'downloads/'

function log(ok, msg) {
  results.push({ ok, msg })
  console.log(`${ok ? '✅' : '❌'} ${msg}`)
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ acceptDownloads: true })
const page = await context.newPage({ viewport: { width: 1280, height: 900 } })

try {
  // ---------- 1. 注册 → 生成文章（复用之前验证的流程，直接走最短路径） ----------
  await page.goto(`${BASE}/register`, { waitUntil: 'networkidle' })
  await page.getByPlaceholder('手机号').fill(phone)
  await page.getByPlaceholder('昵称（可选）').fill('导出验证用户')
  await page.getByPlaceholder('密码（至少 6 位）').fill('test123456')
  await page.getByPlaceholder('确认密码').fill('test123456')
  await page.locator('button:has-text("注 册")').click()
  await page.waitForURL('**/')

  await page.getByPlaceholder(/输入创作主题或关键词/).fill('职场效率')
  await page.locator('button:has-text("一键生成爆文")').click()
  await page.waitForSelector('.topic-item', { timeout: 60000 })
  await page.locator('.topics-action button').first().click()
  await page.waitForSelector('text=创作完成', { timeout: 240000 })
  log(true, '文章创作完成')

  // ---------- 2. 生成配图（1 张，快速） ----------
  await page.locator('button:has-text("✨ 生成配图")').click()
  await page.waitForSelector('.image-grid .el-image img', { timeout: 180000 })
  const imgCount = await page.locator('.image-grid .el-image img').count()
  log(imgCount >= 1, `配图生成 ${imgCount} 张`)

  // ---------- 3. 导出 Markdown（下载文件并检查内容） ----------
  const [mdDownload] = await Promise.all([
    page.waitForEvent('download'),
    page.locator('button:has-text("导出 Markdown")').click(),
  ])
  const mdPath = await mdDownload.path()
  const fs = await import('fs')
  const mdContent = fs.readFileSync(mdPath, 'utf-8')
  log(mdContent.includes('![配图1]'), 'MD 文件包含图片引用 ![配图1]')
  log(mdContent.includes('127.0.0.1:8001/images/'), 'MD 图片引用使用后端绝对 URL')
  log(mdContent.includes('# '), 'MD 包含标题')
  log(true, `MD 下载成功（${mdContent.length} 字符）`)

  // ---------- 4. 导出 HTML（检查 base64 内嵌） ----------
  const [htmlDownload] = await Promise.all([
    page.waitForEvent('download'),
    page.locator('button:has-text("导出 HTML")').click(),
  ])
  const htmlPath = await htmlDownload.path()
  const htmlContent = fs.readFileSync(htmlPath, 'utf-8')
  log(htmlContent.includes('data:image/png;base64,'), 'HTML 内嵌 base64 图片（data:image）')
  log(htmlContent.includes('<!DOCTYPE html>'), 'HTML 是完整文档')
  log(true, `HTML 下载成功（${htmlContent.length} 字符）`)
} catch (err) {
  log(false, `验证中断: ${err.message}`)
} finally {
  await browser.close()
}

const failed = results.filter((r) => !r.ok).length
console.log(`\n========== 结果汇总: ${results.length - failed}/${results.length} 通过 ==========`)
if (failed > 0) process.exit(1)
