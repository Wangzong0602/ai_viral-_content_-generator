"""
网页正文抓取服务（异步）：从文章链接提取标题和正文

【用途】
爆文逆向分析支持两种输入：
1. 直接粘贴文章内容（主要方式，最可靠）
2. 粘贴文章链接（本模块负责抓取网页提取正文）

【实现说明】
- httpx 异步抓取 HTML（不阻塞事件循环）
- BeautifulSoup 解析：提取 <title> 和正文段落
- 反爬兜底：很多平台（小红书/知乎等）有反爬机制，
  抓取失败时返回可读的错误提示，引导用户直接粘贴内容

【正文提取策略】
优先尝试常见正文容器（article / main / post-content 等），
找不到就退化为"提取所有 <p> 段落文本"。
"""

import asyncio
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.exceptions import BizException
from app.core.logger import logger

# 抓取超时（秒）
FETCH_TIMEOUT: float = 15.0
# 请求头：模拟浏览器，降低被反爬拦截的概率
FETCH_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 常见正文容器（按优先级尝试）
CONTENT_SELECTORS: list[str] = [
    "article",
    "main",
    ".post-content",
    ".article-content",
    ".rich_media_content",
    ".content",
    "#content",
]


def _looks_like_url(text: str) -> bool:
    """判断输入是否像链接（http/https 开头）。"""
    return text.strip().lower().startswith(("http://", "https://"))


def _extract_text(soup: BeautifulSoup) -> tuple[str, str]:
    """
    从 HTML 中提取标题和正文。

    :param soup: 解析后的 HTML
    :return: (标题, 正文) —— 提取不到正文时正文为空串
    """
    # 标题：<title> 标签（去掉 " - 站点名" 后缀）
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    if title:
        title = re.split(r"\s*[|–—-]\s*", title)[0].strip()

    # 正文：优先尝试常见容器
    for selector in CONTENT_SELECTORS:
        container = soup.select_one(selector)
        if container:
            # 取容器内所有段落文本（跳过 script/style）
            paragraphs = [
                p.get_text(strip=True)
                for p in container.find_all(["p", "h1", "h2", "h3", "li"])
                if p.get_text(strip=True)
            ]
            text = "\n".join(paragraphs)
            if len(text) > 200:  # 足够长才认为提取成功
                return title, text

    # 兜底：提取所有 <p>
    paragraphs = [
        p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)
    ]
    return title, "\n".join(paragraphs)


async def fetch_article(url: str) -> dict:
    """
    抓取文章链接，提取标题和正文。

    :param url: 文章链接
    :return: {"title": str, "content": str}
    :raises BizException: 抓取失败/无正文时抛出（提示用户改粘贴内容）
    """
    # 校验 URL 格式
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise BizException("链接格式不正确，请检查后重试", status_code=422)

    logger.info("开始抓取文章: %s", url)
    try:
        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT, headers=FETCH_HEADERS, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as exc:
        logger.warning("文章抓取失败 url=%s: %s", url, exc)
        raise BizException(
            "文章抓取失败（可能是平台有反爬限制），建议直接粘贴文章内容",
            status_code=502,
        )

    # 解析 HTML 提取标题和正文（同步解析较快，直接调用）
    soup = await asyncio.to_thread(BeautifulSoup, html, "html.parser")
    title, content = await asyncio.to_thread(_extract_text, soup)

    if len(content) < 100:
        logger.warning("提取到的正文过短 url=%s len=%d", url, len(content))
        raise BizException(
            "未能提取到正文（可能是页面需要登录/有反爬），建议直接粘贴文章内容",
            status_code=422,
        )

    logger.info("文章抓取成功: 标题=%s 正文=%d 字", title, len(content))
    return {"title": title, "content": content}
