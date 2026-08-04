"""
排版整合智能体（Layout Agent）：按平台风格排版

【角色定位】
排版设计师：让文案符合各平台的发布规范。

【输入】润色后的文案 + 目标平台
【输出】排版后的最终文案

【为什么排版还要用 AI？】
各平台对"发布格式"有隐性偏好（小红书要话题标签、公众号要分段分节）：
- 小红书：文末加话题标签（#xxx #yyy）
- 公众号：长文建议有小标题分割
- 知乎：逻辑严谨，可加"---"分隔

MVP 阶段先用"规则 + 简单 AI 辅助"：规则负责确定性的部分
（如话题标签），AI 负责把正文按平台风格重组（如拆分段落、加小标题）。
"""

from app.services.ai_service import chat

# 排版整合智能体的系统提示词（图文爆文）
LAYOUT_AGENT_PROMPT = """
你是一位新媒体排版专家，擅长把文章排版成符合平台规范的形式。

【平台排版规范】
- 小红书：短句分段、适当 Emoji、文末加 3-5 个话题标签（#关键词 格式）
- 公众号：段落分明、可添加小标题、正文连贯
- 知乎：逻辑层次清晰、可使用小标题和分隔

【任务】
将用户提供的文案重新排版：
1. 按平台规范调整段落结构
2. 小红书需要在文末追加相关话题标签
3. 保留全部正文内容，不要删减或改写原文

直接输出排版后的完整文案，不要解释过程，不要输出 JSON。
"""

# 非图文形态的排版提示词（P3 扩展）：
# 脚本/直播/带货文案的结构由创作节点保证，排版只做轻量整理，
# 不追加话题标签（脚本发布时标签由用户自行决定）
SCRIPT_LAYOUT_PROMPT = """
你是一位内容排版助手，负责把创作脚本整理成易读的发布稿。

【任务】
1. 保持原文内容一字不改（不要删减、不要改写、不要总结）
2. 只做轻量整理：统一空行分段、把已有结构标记（如【开场】）排版清晰
3. 不要追加话题标签、不要加 Emoji

直接输出整理后的完整内容，不要解释过程，不要输出 JSON。
"""


def layout_content(content: str, platform: str, content_type: str = "article") -> str:
    """
    对润色后的文案进行排版（一次性调用）。

    :param content: 润色后的文案
    :param platform: 目标平台（小红书/公众号/知乎）
    :param content_type: 内容形态（article 按平台排版，脚本类只做轻量整理）
    :return: 排版后的最终文案
    """
    # 脚本/直播/带货形态：结构已定，只做轻量整理，避免 AI 乱改脚本
    if content_type != "article":
        user_prompt = f"""
【内容形态】{content_type}

【文案】
{content}

请整理排版后输出。
"""
        return chat(
            system_prompt=SCRIPT_LAYOUT_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=4096,
        )

    user_prompt = f"""
【目标平台】{platform}

【文案】
{content}

请按平台规范排版后输出。
"""
    return chat(
        system_prompt=LAYOUT_AGENT_PROMPT,
        user_prompt=user_prompt,
        temperature=0.3,  # 排版是"确定性"工作，温度要低，防止乱改内容
        max_tokens=4096,
    )
