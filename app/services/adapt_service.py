"""
多平台适配服务（异步）：把一篇文章改写成多个平台版本

【与排版智能体的区别】
- layout_agent：只做"排版"（分段/标签/结构），保留原文
- adapt（本模块）：做"改写"——按平台风格重写（小红书更口语+emoji、
  公众号更正式、知乎更专业），是更强的风格适配

【平台风格与字数规范】（来自各平台真实发布规范）
- 小红书（图文笔记）：300-700 字（最优区间，超长会被限流）
- 知乎：1500-3000 字（最优区间）
- 公众号：1200-3000 字（大众账号黄金区间）

【字数保障机制（企业级质量把控）】
光靠提示词约束不可靠（模型经常超写），所以：
1. 提示词里明确字数区间
2. 生成后后端【实测字数】校验
3. 超出上限 → 自动让模型压缩一次（把"当前字数+目标字数"告诉模型）
4. 压缩后仍超 → 返回结果并附 warning（不无限重试烧钱）

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
你是一位资深小红书笔记写手，擅长把文章改写成高互动的小红书图文笔记。

【平台规范（重要！）】
小红书图文笔记的字数最优区间是 300-700 字（不算话题标签），
超过 700 字会降低完读率、被算法限流。必须严格遵守！

【改写要求】
1. 口语化、亲切感强，像和朋友聊天
2. 多用短句和 Emoji（每段 1-2 个），增强情绪表达
3. 结构：开头痛点共鸣 → 干货分点 → 结尾引导互动
4. 文末加 3-5 个相关话题标签（#关键词 格式，标签不算正文字数）
5. 保留原文最核心的信息和亮点，果断删掉次要内容（这是小红书逻辑）
6. 【字数硬性要求】正文控制在 300-700 字，宁短勿长

直接输出改写后的完整文案（含文末标签），不要解释过程，不要输出 JSON。
""",
    "公众号": """
你是一位资深公众号编辑，擅长把文章改写成公众号长文的风格。

【平台规范（重要！）】
大众公众号文章的黄金字数区间是 1200-3000 字。

【改写要求】
1. 表达正式严谨、逻辑清晰、观点输出强
2. 结构：标题式开头 → 分节展开（可加小标题）→ 总结升华
3. 段落分明，信息密度高，引用数据或案例增强说服力
4. 语言专业但不晦涩，适合职场/知识类读者
5. 保留原文全部核心内容，可适当扩充论述
6. 【字数硬性要求】控制在 1200-3000 字

直接输出改写后的完整文案，不要解释过程，不要输出 JSON。
""",
    "知乎": """
你是一位知乎高赞答主，擅长把文章改写成专业理性的知乎回答。

【平台规范（重要！）】
知乎优质回答的字数最优区间是 1500-3000 字。

【改写要求】
1. 开头直接给出核心观点（结论前置）
2. 论证充分：分点展开，每点有理有据（可补充数据/案例/逻辑推演）
3. 语言克制客观，避免夸张情绪化表达
4. 适当使用"首先/其次/最后""总结"等逻辑连接词
5. 保留原文核心信息，增加专业深度
6. 【字数硬性要求】控制在 1500-3000 字

直接输出改写后的完整文案，不要解释过程，不要输出 JSON。
""",
}

# 各平台字数上限（硬性校验用）：超过则触发压缩重写
PLATFORM_LENGTH_LIMITS: dict[str, tuple[int, int]] = {
    "小红书": (300, 700),  # 最优区间
    "公众号": (1200, 3000),
    "知乎": (1500, 3000),
}

# 超长时压缩重写的系统提示词（把实测字数反馈给模型）
COMPRESS_PROMPT = """
你是一位资深新媒体编辑。你之前改写的文章【超长】了，不符合平台字数规范。
请把文章压缩到指定字数区间内：
1. 保留核心观点和最重要的信息
2. 删除重复、冗余、次要的细节
3. 保持平台风格（口语化/正式/专业）不变
4. 直接输出压缩后的完整文案，不要解释过程，不要输出 JSON
"""

# 兜底：未知平台的通用改写提示词
DEFAULT_ADAPT_PROMPT = """
你是一位资深新媒体编辑，请把文章改写成适合【{platform}】平台发布的版本。
保留核心信息，调整表达风格适应该平台读者。直接输出改写后的完整文案。
"""


def _call_adapt(system_prompt: str, user_prompt: str) -> str:
    """同步调用大模型（放线程池执行）。"""
    return chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.6,
        max_tokens=4096,
    )


async def _adapt_with_length_check(content: str, platform: str) -> dict:
    """
    改写单篇文章为指定平台版本，并做字数校验。

    【字数保障流程】
    1. 首次改写（提示词已含字数规范）
    2. 实测字数：超上限 → 让模型压缩（反馈当前字数 + 目标区间）
    3. 压缩后仍超 → 返回结果 + warning（不无限重试）

    :param content: 原文
    :param platform: 目标平台
    :return: {"content": str, "warning": str} —— warning 非空表示字数未完全达标
    :raises BizException: 改写失败时抛出
    """
    system_prompt = ADAPT_PROMPTS.get(platform, DEFAULT_ADAPT_PROMPT.format(platform=platform))
    limit = PLATFORM_LENGTH_LIMITS.get(platform)

    user_prompt = f"""
【目标平台】{platform}

【原文】
{content}

请改写成适合该平台发布的版本。
"""
    try:
        # ---------- 1. 首次改写 ----------
        adapted = await asyncio.to_thread(_call_adapt, system_prompt, user_prompt)
        if not adapted or not adapted.strip():
            raise BizException(f"{platform} 适配结果为空", status_code=502)

        # ---------- 2. 字数校验（有规范区间时） ----------
        warning = ""
        if limit:
            min_len, max_len = limit
            actual = len(adapted)
            if actual > max_len:
                # 超上限 → 压缩一次（把实测字数反馈给模型，目标更明确）
                logger.info(
                    "%s 首次改写 %d 字，超出上限 %d，触发压缩",
                    platform, actual, max_len,
                )
                compress_prompt = f"""
【目标平台】{platform}
【当前字数】{actual} 字（超长了）
【目标字数】{min_len}-{max_len} 字（必须压缩到这个区间）

【当前超长的文案】
{adapted}

请压缩并直接输出。
"""
                compressed = await asyncio.to_thread(
                    _call_adapt, COMPRESS_PROMPT, compress_prompt
                )
                if compressed and compressed.strip():
                    adapted = compressed
                    actual = len(adapted)
                    if actual > max_len:
                        warning = f"字数仍超出推荐区间（{actual} 字，推荐 {min_len}-{max_len}）"
                        logger.warning("%s 压缩后仍 %d 字", platform, actual)
                    else:
                        logger.info("%s 压缩完成: %d 字", platform, actual)
            elif actual < min_len:
                # 过短：附 warning（不强制扩写，避免注水）
                warning = f"字数偏少（{actual} 字，推荐 {min_len}-{max_len}）"
                logger.info("%s 字数偏少: %d 字", platform, actual)

        return {"content": adapted, "warning": warning}
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
        {"platform": str, "content": str, "success": bool, "error": str, "warning": str}
    """
    logger.info("开始多平台适配: platforms=%s", platforms)

    # 并发改写每个平台（单个失败不影响其他）
    results = await asyncio.gather(
        *[_adapt_with_length_check(content, p) for p in platforms],
        return_exceptions=True,
    )

    # 组装结果
    out: list[dict] = []
    for platform, res in zip(platforms, results):
        if isinstance(res, dict) and res.get("content"):  # 成功
            out.append({
                "platform": platform,
                "content": res["content"],
                "success": True,
                "error": "",
                "warning": res.get("warning", ""),
            })
        else:  # 失败（BizException 已被 _adapt_with_length_check 记录日志）
            out.append({
                "platform": platform,
                "content": "",
                "success": False,
                "error": str(res) if not isinstance(res, dict) else "适配失败",
                "warning": "",
            })

    # 全部失败则整体报错（前端可以友好提示）
    if not any(r["success"] for r in out):
        raise BizException("所有平台适配均失败，请稍后重试", status_code=502)

    logger.info("多平台适配完成: %d/%d 成功", sum(1 for r in out if r["success"]), len(out))
    return out
