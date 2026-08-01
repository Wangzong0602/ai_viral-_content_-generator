"""
图片本地存储服务（异步）

【职责】
把 AI 生成的图片（远端临时 URL）异步下载到本地磁盘，返回本地访问 URL。

【为什么必须下载到本地？】
通义万相返回的图片 URL 是"临时链接"（带 Expires 过期参数，一般 24 小时失效），
如果直接存这个 URL 给用户，过几天图就裂了。所以：
1. 下载图片二进制到本地磁盘（data/images/）
2. 通过 FastAPI 静态目录（/images）对外提供访问
3. 返回的 URL 永久有效（本地文件）

【目录结构设计】
data/images/YYYYMMDD/<uuid>.png
- 按日期分目录：方便按天清理过期图片（运维策略）
- uuid 文件名：避免重名、避免路径注入（不信任外部输入）
"""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.exceptions import BizException
from app.core.logger import logger

# 图片存储根目录的绝对路径（由配置的相对路径解析）
IMAGE_ROOT: Path = Path(settings.IMAGE_STORAGE_DIR)
IMAGE_URL_PREFIX: str = settings.IMAGE_URL_PREFIX

# 下载超时：生成出的图可能较大（1-3MB），给 60 秒充足时间
DOWNLOAD_TIMEOUT: float = 60.0


def _ensure_dir(date_dir: Path) -> None:
    """确保目录存在（并发安全：exist_ok=True 时多线程同时创建不报错）。"""
    date_dir.mkdir(parents=True, exist_ok=True)


async def download_and_save(remote_url: str, ext: str = ".png") -> str:
    """
    下载远端图片并保存到本地，返回本地访问 URL。

    【执行流程】
    1. 生成存储路径：data/images/YYYYMMDD/<uuid><ext>
    2. 异步下载图片二进制（httpx.AsyncClient，不阻塞事件循环）
    3. 写入本地文件（小文件用异步写；aiofiles 可选，1-3MB 用 asyncio.to_thread 足够）
    4. 返回本地 URL：/images/YYYYMMDD/<uuid>.png

    :param remote_url: 通义万相返回的临时图片 URL
    :param ext: 图片扩展名（默认 .png）
    :return: 本地可访问的 URL（以 IMAGE_URL_PREFIX 开头）
    :raises BizException: 下载失败时抛出（由全局异常处理器返回 502）
    """
    # ---------- 1. 构造存储路径 ----------
    today = datetime.now().strftime("%Y%m%d")
    date_dir = IMAGE_ROOT / today
    _ensure_dir(date_dir)  # 同步创建目录（mkdir 是快速操作，可接受）
    filename = f"{uuid.uuid4().hex}{ext}"
    target_path = date_dir / filename

    # ---------- 2. 异步下载 ----------
    try:
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
            resp = await client.get(remote_url)
            resp.raise_for_status()  # 非 2xx 状态码抛异常
    except Exception as exc:
        logger.error("图片下载失败 url=%s: %s", remote_url, exc)
        raise BizException("图片下载失败，请重试", status_code=502)

    # ---------- 3. 异步写入本地文件 ----------
    # asyncio.to_thread：把"同步文件写入"放到线程池执行，避免阻塞事件循环
    # （图片 1-3MB，线程池写文件是标准做法）
    await asyncio.to_thread(_write_file, target_path, resp.content)

    # ---------- 4. 返回本地 URL ----------
    relative = target_path.relative_to(IMAGE_ROOT).as_posix()  # 转成 / 分隔
    url = f"{IMAGE_URL_PREFIX}/{relative}"
    logger.info("图片已保存: %s (%d bytes)", url, len(resp.content))
    return url


def _write_file(path: Path, content: bytes) -> None:
    """同步写文件（放到线程池执行）。分离出来便于单元测试。"""
    with open(path, "wb") as f:
        f.write(content)
