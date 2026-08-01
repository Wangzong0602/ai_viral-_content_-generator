"""
爆文逆向分析服务：组合「抓取文章」+「AI 拆解要素」

【执行流程】
1. 判断输入类型：链接 → 先抓取正文；内容 → 直接用
2. 调用 viral_analyzer 智能体拆解爆文要素
3. 返回分析报告

【输入长度控制】
- 粘贴内容：截断到 8000 字（viral_analyzer 内部处理）
- 链接抓取：正文超过 8000 字也截断（分析时处理）
"""

import asyncio

from app.core.exceptions import BizException
from app.core.logger import logger
from app.agents.viral_analyzer import analyze_article
from app.services.article_fetcher import _looks_like_url, fetch_article


async def analyze_viral_article(input_text: str) -> dict:
    """
    逆向分析一篇爆文（支持链接或直接内容）。

    :param input_text: 文章链接 或 文章内容
    :return: 分析报告：
        {
          "title": 标题（链接抓取时有值，内容输入时为空或 None）,
          "content_len": 正文长度,
          "report": {title_hook, opening_3s, ...}
        }
    :raises BizException: 输入太短/分析失败时抛出
    """
    # ---------- 1. 输入预处理 ----------
    input_text = input_text.strip()
    if len(input_text) < 50:
        raise BizException("内容太短，请提供完整的文章（至少 50 字）", status_code=422)

    title: str = ""
    content: str = ""

    # ---------- 2. 链接 → 抓取；否则直接用内容 ----------
    if _looks_like_url(input_text):
        logger.info("检测到链接输入，尝试抓取...")
        article = await fetch_article(input_text)
        title = article["title"]
        content = article["content"]
    else:
        content = input_text

    # ---------- 3. 调用智能体拆解（线程池执行，避免阻塞事件循环） ----------
    logger.info("开始爆文逆向分析, 正文 %d 字", len(content))
    report = await asyncio.to_thread(analyze_article, content, title)

    # 解析失败兜底
    if not report:
        raise BizException("分析失败，请稍后重试", status_code=502)

    logger.info("爆文逆向分析完成")
    return {
        "title": title,
        "content_len": len(content),
        "report": report,
    }
