"""
AI 配图服务（异步）：语义分析 → 生成配图 Prompt → 调通义万相 → 本地存储

【配图流程】
1. 语义分析：把文案交给通义千问，提取"配图主题"（关键场景/情绪/风格）
   ——让 AI 理解内容，而不是用户手动描述
2. 生成配图：调通义万相（wanx2.1-t2i-turbo）生成图片
3. 本地存储：下载图片到本地磁盘（image_storage 模块），返回本地 URL

【并发生成】
一次请求生成多张图（默认 3 张），用 asyncio.gather 并发调用：
- 3 张图并行生成（每张约 10-20 秒），总耗时接近单张而非 3 倍
- 任一张失败不影响其他（gather 带 return_exceptions 收集结果）
"""

import asyncio
from typing import Any

from dashscope import ImageSynthesis

from app.core.config import settings
from app.core.exceptions import BizException
from app.core.logger import logger
from app.services.ai_service import chat
from app.services.image_storage import download_and_save

# 支持的配图风格（前端选择，映射成提示词里的风格描述）
STYLES: dict[str, str] = {
    "插画卡通": "明亮鲜艳的插画卡通风格",
    "写实摄影": "高清晰度的写实摄影风格",
    "科技未来": "科技感十足的科幻未来风格",
    "简约扁平": "简洁大方的扁平化设计风格",
    "国潮古风": "传统中国风元素与现代设计结合",
}

# 并发控制：通义万相有速率限制（实测 3 并发触发 429），
# 用信号量限制同时进行的图像生成任务数，避免限流
IMAGE_CONCURRENCY = 2
# 429 限流时的最大重试次数（指数退避 + 抖动）
IMAGE_MAX_RETRIES = 3
# 429 重试的基础等待秒数（退避：2s → 4s → 8s）
IMAGE_RETRY_BASE_DELAY = 2.0

# 全局信号量：限制并发生成图片数量
_image_semaphore = asyncio.Semaphore(IMAGE_CONCURRENCY)


# 配图语义分析的系统提示词
IMAGE_ANALYZER_PROMPT = """
你是一位资深的新媒体视觉策划师，擅长从文章中提炼配图主题。
请分析用户提供的文章，提取出最值得配图的场景主题。

【要求】
- 每个主题用一句话描述画面（包括场景、元素、情绪）
- 主题之间要有区分度（不要重复）
- 语言简洁具体，适合作为图像生成提示词

【输出格式】
必须严格按照以下 JSON 格式输出，不要输出任何其他内容：
{
  "scenes": ["主题1", "主题2", "主题3"]
}
"""


async def _generate_one_image(scene_prompt: str, style_desc: str) -> str:
    """
    生成单张图片并保存到本地（带并发限制 + 429 退避重试）。

    【为什么用 dashscope 原生 SDK 而不是 OpenAI 兼容接口？】
    通义万相图像生成走"异步任务"模式（提交任务 → 轮询结果），
    OpenAI 兼容模式未提供 images 接口（已实测 404）。
    ImageSynthesis.call 内部会同步轮询任务，所以用 asyncio.to_thread
    放到线程池执行，避免阻塞事件循环（符合 async 规范）。

    【企业级可靠性】
    - 信号量：同一时刻最多 IMAGE_CONCURRENCY 张图在生成（避免 429 限流）
    - 429 重试：命中限流（Throttling.RateQuota）时指数退避重试，最多 3 次

    :param scene_prompt: 场景描述（来自语义分析）
    :param style_desc: 风格描述（来自 STYLES 映射）
    :return: 本地图片 URL
    """
    full_prompt = f"{scene_prompt}，{style_desc}"

    async def _call_with_retry() -> Any:
        """
        带 429 退避重试的调用（在信号量内执行）。
        返回通义万相响应对象（成功后 status_code=200）。
        """
        for attempt in range(IMAGE_MAX_RETRIES):
            rsp = await asyncio.to_thread(
                lambda: ImageSynthesis.call(
                    api_key=settings.DASHSCOPE_API_KEY,
                    model=settings.DASHSCOPE_IMAGE_MODEL,
                    prompt=full_prompt,
                    n=1,
                    size=settings.DASHSCOPE_IMAGE_SIZE,
                )
            )
            # 成功
            if rsp.status_code == 200:
                return rsp
            # 429 限流：指数退避后重试
            if rsp.status_code == 429 and attempt < IMAGE_MAX_RETRIES - 1:
                delay = IMAGE_RETRY_BASE_DELAY * (2**attempt)  # 2s → 4s → 8s
                logger.warning(
                    "通义万相限流(429)，%.1f 秒后重试 (第 %d/%d 次)",
                    delay, attempt + 1, IMAGE_MAX_RETRIES,
                )
                await asyncio.sleep(delay)
                continue
            # 其他错误或重试耗尽：抛业务异常
            logger.error("通义万相生成失败: %s %s", rsp.code, rsp.message)
            raise BizException(f"图片生成失败: {rsp.message}", status_code=502)
        raise BizException("图片生成失败: 限流重试耗尽", status_code=502)  # 理论不可达

    try:
        # ---------- 1. 信号量内调用（并发控制） ----------
        async with _image_semaphore:
            rsp = await _call_with_retry()

        # ---------- 2. 提取远端图片 URL 并下载到本地 ----------
        remote_url = rsp.output["results"][0]["url"]
        return await download_and_save(remote_url)
    except BizException:
        raise  # 业务异常直接透传（全局处理器接管）
    except Exception as exc:
        logger.error("图片生成异常 prompt=%s: %s", full_prompt, exc)
        raise BizException("图片生成失败，请稍后重试", status_code=502)


def _extract_scenes(analyze_result: str) -> list[str]:
    """
    解析语义分析结果，提取场景列表。

    :param analyze_result: 模型返回的文本（可能是 JSON 或夹杂文字）
    :return: 场景列表（解析失败时返回空列表）
    """
    from app.agents.base import extract_json

    data = extract_json(analyze_result)
    scenes = data.get("scenes", [])
    # 过滤掉非字符串、空字符串
    return [s for s in scenes if isinstance(s, str) and s.strip()][:5]


async def generate_images(content: str, count: int = 3, style: str = "插画卡通") -> list[str]:
    """
    根据文案生成多张配图（并发）。

    【执行流程】
    1. 语义分析：调通义千问提取配图场景主题（1 次文本调用）
    2. 并发生成：asyncio.gather 同时生成 count 张图
    3. 全部完成后返回本地图片 URL 列表

    :param content: 文章正文（用于语义分析）
    :param count: 生成图片数量（1-5）
    :param style: 风格（必须是 STYLES 的 key，接口层已校验）
    :return: 本地图片 URL 列表（可能少于 count，失败的图被跳过）
    """
    style_desc = STYLES.get(style, STYLES["插画卡通"])  # 兜底默认风格

    # ---------- 1. 语义分析（文本调用，取配图主题） ----------
    logger.info("开始配图语义分析, count=%d style=%s", count, style)
    analyze_text = await asyncio.to_thread(
        chat,
        system_prompt=IMAGE_ANALYZER_PROMPT,
        user_prompt=f"【文章内容】\n{content[:3000]}",  # 截断：避免超长输入
        temperature=0.5,
        max_tokens=1024,
    )
    scenes = _extract_scenes(analyze_text)
    if not scenes:
        # 语义分析失败：用文章前 100 字作为兜底场景
        logger.warning("语义分析未提取到场景，使用兜底")
        scenes = [content[:100]]
    logger.info("语义分析完成, 提取到 %d 个场景", len(scenes))

    # ---------- 2. 并发生成图片 ----------
    # 取前 count 个场景；场景不足时重复最后一个补足
    tasks = [scenes[i % len(scenes)] for i in range(count)]
    results: list[list[str]] = await asyncio.gather(
        *[_generate_one_image(scene, style_desc) for scene in tasks],
        return_exceptions=True,  # 单张失败不中断其他
    )

    # ---------- 3. 收集成功的图片 URL ----------
    urls: list[str] = []
    for i, res in enumerate(results):
        if isinstance(res, str):  # 成功：是 URL 字符串
            urls.append(res)
        else:  # 失败：Exception（BizException 已在 _generate_one_image 抛出时记录）
            logger.warning("第 %d 张图片生成失败: %s", i + 1, res)

    if not urls:
        raise BizException("图片生成全部失败，请稍后重试", status_code=502)
    return urls
