"""
AI 配图服务（异步）：语义分析 → 生成配图 Prompt → 调通义万相 → 本地存储

【配图流程】
1. 语义分析：把文案交给通义千问，提取"配图主题"（关键场景/情绪/风格）
   ——让 AI 理解内容，而不是用户手动描述
2. 生成配图：调通义万相（支持 wan2.7-image-pro 高质量模型）生成图片
3. 本地存储：下载图片到本地磁盘（image_storage 模块），返回本地 URL

【并发生成】
一次请求生成多张图（默认 3 张），用 asyncio.gather 并发调用：
- 3 张图并行生成（每张约 20-40 秒），总耗时接近单张而非 3 倍
- 任一张失败不影响其他（gather 带 return_exceptions 收集结果）
"""

import asyncio
from typing import Any

from app.core.config import settings
from app.core.exceptions import BizException
from app.core.logger import logger
from app.services.ai_service import chat
from app.services.image_generation_service import image_generation_service

# 支持的配图风格（前端选择，映射成提示词里的风格描述）
STYLES: dict[str, str] = {
    "插画卡通": "明亮鲜艳的插画卡通风格",
    "写实摄影": "高清晰度的写实摄影风格",
    "科技未来": "科技感十足的科幻未来风格",
    "简约扁平": "简洁大方的扁平化设计风格",
    "国潮古风": "传统中国风元素与现代设计结合",
}

# 各风格的"去AI味"高级提示词增强（光线、质感、细节、构图）
STYLE_PROMPTS: dict[str, str] = {
    "插画卡通": (
        "充满手绘质感的插画风格，笔触自然，色彩柔和有层次，"
        "有纸张纹理，避免塑料感，人物表情生动自然，构图有呼吸感"
    ),
    "写实摄影": (
        "专业摄影棚或真实场景的写实风格，自然光线（晨光/窗光），"
        "景深适中，细节丰富（皮肤纹理/材质/阴影过渡自然），"
        "避免过度磨皮和数字感，像用单反相机拍摄的真实照片"
    ),
    "科技未来": (
        "高级科技感视觉，深色背景配霓虹光效，金属质感真实，"
        "光影层次丰富，构图简洁有未来感，避免廉价3D渲染感"
    ),
    "简约扁平": (
        "专业平面设计风格，构图留白充分，配色克制高级，"
        "图标和图形边缘清晰，整体干净现代，避免元素堆砌"
    ),
    "国潮古风": (
        "中国风插画，水墨晕染或工笔质感，传统纹样点缀，"
        "配色典雅（朱砂/黛蓝/鎏金），氛围感强，细节考究"
    ),
}

# 通用负面提示词（告诉模型避免什么 = 降低"AI味"关键手段）
NEGATIVE_PROMPT = (
    "低质量，模糊，水印，文字乱码，过度饱和，塑料质感，"
    "僵硬表情，不自然光影，AI生成感，虚假细节"
)

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


async def _generate_one_image(scene_prompt: str, style_desc: str, style_key: str) -> str:
    """
    生成单张图片并保存到本地（带并发限制）。

    使用新的 image_generation_service，自动支持：
    - wanx2.1-t2i-turbo：旧版 API（快速低质量）
    - wan2.7-image-pro：新版 messages API（高质量）

    【去AI味优化】
    - 风格增强提示词（光线/质感/细节/构图）
    - 负面提示词（避免塑料感/过度饱和/数字感）

    :param scene_prompt: 场景描述（来自语义分析）
    :param style_desc: 风格描述（来自 STYLES 映射）
    :param style_key: 风格 key（用于取 STYLE_PROMPTS 增强提示词）
    :return: 本地图片 URL
    """
    # 组合高质量提示词：场景 + 风格增强描述
    style_enhance = STYLE_PROMPTS.get(style_key, "")
    full_prompt = f"{scene_prompt}。{style_desc}，{style_enhance}".strip("，")

    try:
        # 信号量内生成（并发控制）
        async with _image_semaphore:
            urls = await image_generation_service.generate(
                prompt=full_prompt,
                size=settings.DASHSCOPE_IMAGE_SIZE,
                n=1,
                model=settings.DASHSCOPE_IMAGE_MODEL,
                negative_prompt=NEGATIVE_PROMPT,
            )
        
        if not urls:
            raise BizException("图片生成失败：未返回图片", status_code=502)
        
        return urls[0]  # 只生成 1 张，返回第一个 URL
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
        *[_generate_one_image(scene, style_desc, style) for scene in tasks],
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
