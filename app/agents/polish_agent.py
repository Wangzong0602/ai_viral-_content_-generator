"""
润色优化智能体（Polish Agent）：打磨语言、增强情绪

【角色定位】
语言大师：把初稿改得更口语化、更有情绪张力、更符合平台风格。

【输入】初稿文案 + 目标平台
【输出】润色后的文案

【每个平台的语言风格差异】
- 小红书：短句 + Emoji + 轻松活泼
- 公众号：长段落 + 正式严谨 + 观点输出强
- 知乎：专业理性 + 论据充分 + 数据支撑
"""

from app.services.ai_service import chat_stream

# 润色优化智能体的系统提示词
POLISH_AGENT_PROMPT = """
你是一位资深的语言润色专家，擅长优化文字表达、增强情绪价值。

【润色要求】
1. 语言口语化、接地气（"你有没有遇到过..."这类表达）
2. 增强情绪价值（适当加入"太震撼了""必须收藏"等情绪化表达）
3. 优化段落节奏（多用短句、适当留白）
4. 保持原文的核心内容、观点、信息量不变

【平台风格调整】
- 小红书：短句 + 适当 Emoji + 轻松活泼
- 公众号：长段落 + 正式严谨 + 逻辑清晰
- 知乎：专业理性 + 论据充分 + 表达克制

【任务】
把用户提供的初稿润色成更优质、更有感染力的版本。
直接输出润色后的完整文案，不要解释过程，不要输出 JSON。
"""


def stream_polish(draft: str, platform: str):
    """
    流式润色文案（SSE 使用）。

    :param draft: 文案创作智能体生成的初稿
    :param platform: 目标平台（决定润色风格）
    :return: 生成器，逐个产出润色后的增量文本片段
    """
    user_prompt = f"""
【目标平台】{platform}

【初稿】
{draft}

请输出润色后的完整文案。
"""
    # 温度低一些：润色要忠于原文，不宜过度发挥
    yield from chat_stream(
        system_prompt=POLISH_AGENT_PROMPT,
        user_prompt=user_prompt,
        temperature=0.5,
        max_tokens=4096,
    )
