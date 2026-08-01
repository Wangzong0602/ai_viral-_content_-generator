"""
多平台适配服务（异步）：把一篇文章改写成多个平台版本

【与排版智能体的区别】
- layout_agent：只做"排版"（分段/标签/结构），保留原文
- adapt（本模块）：做"改写"——按平台风格重写（小红书更口语+emoji、
  公众号更正式、知乎更专业），是更强的风格适配

【平台风格策略】
- 小红书：短句 + Emoji + 口语化 + 文末话题标签（内容要"种草感"）
- 公众号：长段落 + 正式严谨 + 观点输出 + 可加小标题
- 知乎：专业理性 + 论据充分 + 数据支撑 + 逻辑分层

【并发生成】
多个平台同时改写用 asyncio.gather 并发：
- 每个平台独立调用大模型，互不影响
- 单个平台失败不影响其他（gather 收集结果）
"""

import asyncio

from app.core.exceptions import BizException
from app.core.logger import logger
from app.services.ai_service import chat

# 各平台的适配提示词（改写强度更高，不只是排版）
ADAPT_PROMPTS: dict[str, str] = {
    "小红书": """
你是一位资深小红书笔记写手，擅长把文章改写成高互动的小红书笔记。

【改写要求】
1. 口语化、亲切感强，像和朋友聊天
2. 多用短句和 Emoji（每段 1-2 个），增强情绪表达
3. 结构：开头痛点共鸣 → 干货分点 → 结尾引导互动
4. 文末加 3-5 个相关话题标签（#关键词 格式）
5. 保留原文核心信息和观点，但表达方式完全小红书化
6. 1000-1500 字左右（删减冗余，保留精华）

直接输出改写后的完整文案，不要解释过程，不要输出 JSON。
""",
    "公众号": """
你是一位资深公众号编辑，擅长把文章改写成公众号长文的风格。

【改写要求】
1. 表达正式严谨、逻辑清晰、观点输出强
2. 结构：标题式开头 → 分节展开（可加小标题）→ 总结升华
3. 段落分明，信息密度高，引用数据或案例增强说服力
4. 语言专业但不晦涩，适合职场/知识类读者
5. 保留原文全部核心内容，可适当扩充论述
6. 2000-3000 字左右

直接输出改写后的完整文案，不要解释过程，不要输出 JSON。
""",
    "知乎": """
你是一位知乎高赞答主，擅长把文章改写成专业理性的知乎回答。

【改写要求】
1. 开头直接给出核心观点（结论前置）
2. 论证充分：分点展开，每点有理有据（可补充数据/案例/逻辑推演）
3. 语言克制客观，避免夸张情绪化表达
4. 适当使用"首先/其次/最后""总结"等逻辑连接词
5. 保留原文核心信息，增加专业深度
6. 1500-2500 字左右

直接输出改写后的完整文案，不要解释过程，不要输出 JSON。
""",
}

# 兜底：未知平台的通用改写提示词
DEFAULT_ADAPT_PROMPT = """
你是一位资深新媒体编辑，请把文章改写成适合【{platform}】平台发布的版本。
保留核心信息，调整表达风格适应该平台读者。直接输出改写后的完整文案。
"""


async def _adapt_single(content: str, platform: str) -> str:
    """
    改写单篇文章为指定平台版本。

    :param content: 原文
    :param platform: 目标平台
    :return: 改写后的文案
    :raises BizException: 改写失败时抛出
    """
    system_prompt = ADAPT_PROMPTS.get(platform, DEFAULT_ADAPT_PROMPT.format(platform=platform))

    user_prompt = f"""
【目标平台】{platform}

【原文】
{content}

请改写成适合该平台发布的版本。
"""
    try:
        # chat 是同步调用（内部同步请求），放线程池执行避免阻塞事件循环
        adapted = await asyncio.to_thread(
            chat,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.6,
            max_tokens=4096,
        )
        # 空结果兜底
        if not adapted or not adapted.strip():
            raise BizException(f"{platform} 适配结果为空", status_code=502)
        return adapted
    except BizException:
        raise
    except Exception as exc:
        logger.error("平台适配失败 platform=%s: %s", platform, exc)
        raise BizException(f"{platform} 适配失败，请稍后重试", status_code=502)


async def adapt_content(content: str, platforms: list[str]) -> list[dict]:
    """
    把一篇文章适配为多个平台版本（并发）。

    :param content: 原文
    :param platforms: 目标平台列表（已去重、已校验）
    :return: 适配结果列表，每项：
        {"platform": str, "content": str, "success": bool, "error": str}
    """
    logger.info("开始多平台适配: platforms=%s", platforms)

    # 并发改写每个平台（单个失败不影响其他）
    results = await asyncio.gather(
        *[_adapt_single(content, p) for p in platforms],
        return_exceptions=True,
    )

    # 组装结果
    out: list[dict] = []
    for platform, res in zip(platforms, results):
        if isinstance(res, str):  # 成功
            out.append({"platform": platform, "content": res, "success": True, "error": ""})
        else:  # 失败（BizException 已被 _adapt_single 记录日志）
            out.append({"platform": platform, "content": "", "success": False, "error": str(res)})

    # 全部失败则整体报错（前端可以友好提示）
    if not any(r["success"] for r in out):
        raise BizException("所有平台适配均失败，请稍后重试", status_code=502)

    logger.info("多平台适配完成: %d/%d 成功", sum(1 for r in out if r["success"]), len(out))
    return out
