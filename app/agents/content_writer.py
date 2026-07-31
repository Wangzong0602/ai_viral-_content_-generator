"""
文案创作智能体（Content Writer）：生成爆文初稿

【角色定位】
资深自媒体文案编辑：基于爆文逻辑报告写出高质量正文。

【输入】选题信息 + 爆文逻辑报告 + 目标平台
【输出】3 个备选标题 + 完整正文初稿

【为什么这个智能体用"流式"输出？】
正文可能 1500-2500 字，一次性等待太久。
流式输出让用户实时看到文字生成过程（打字机效果），
体验好、还能随时感知进度。所以本智能体提供两个函数：
- generate_draft：一次性返回（内部自用/后续扩展）
- stream_draft：流式返回（SSE 接口使用，本次开发用这个）
"""

from app.agents.base import extract_json
from app.services.ai_service import chat, chat_stream

# 文案创作智能体的系统提示词
CONTENT_WRITER_PROMPT = """
你是一位资深的自媒体文案编辑，擅长写爆款标题和高质量正文。

【写作要求】
- 开头：痛点共鸣 + 解决方案预告（按爆文逻辑报告执行）
- 中间：详细内容（分点展开，信息密度高）
- 结尾：总结 + 行动召唤（引导点赞/收藏/评论）
- 语言口语化、接地气，多用短句
- 逻辑清晰、结构完整

【输出格式】
必须严格按照以下 JSON 格式输出，不要输出任何其他内容：
{
  "titles": ["标题1", "标题2", "标题3"],
  "content": "完整正文（1500字以上）"
}
"""


def _build_user_prompt(topic: dict, logic_report: dict, platform: str) -> str:
    """组装文案创作的用户提示词（把选题和逻辑报告嵌入进去）。"""
    return f"""
【选题信息】
- 标题：{topic.get('title', '')}
- 简介：{topic.get('summary', '')}
- 目标平台：{platform}

【爆文逻辑报告】
标题钩子：{logic_report.get('title_hook', '')}
开头策略：{logic_report.get('opening_3s', '')}
内容结构：{logic_report.get('content_structure', '')}
情绪价值点：{logic_report.get('emotion_points', '')}
SEO关键词：{logic_report.get('seo_keywords', '')}

请基于以上策略生成 3 个备选标题和完整正文。
"""


def generate_draft(topic: dict, logic_report: dict, platform: str) -> dict:
    """
    一次性生成文案初稿（非流式）。

    :return: {"titles": [...], "content": "..."}
    """
    text = chat(
        system_prompt=CONTENT_WRITER_PROMPT,
        user_prompt=_build_user_prompt(topic, logic_report, platform),
        temperature=0.7,
        max_tokens=4096,
    )
    data = extract_json(text)
    # 兜底：如果模型没按格式返回，把整段文本当作正文
    if not data.get("content"):
        data = {"titles": [topic.get("title", "")], "content": text}
    return data


def stream_draft(topic: dict, logic_report: dict, platform: str):
    """
    流式生成文案初稿（SSE 使用）。

    【返回的是什么？】
    生成器对象，逐个产出"增量文本片段"。调用方（SSE 接口）拿到后
    一段段推送给前端，前端逐字渲染。

    注意：流式模式无法等到完整 JSON 再解析，
    所以这里不要求模型输出 JSON，直接让它输出"纯正文文本"，
    标题交给前一步的选题标题兜底（保证流程简单可靠）。
    """
    user_prompt = f"""
【选题信息】
- 标题：{topic.get('title', '')}
- 简介：{topic.get('summary', '')}
- 目标平台：{platform}

【爆文逻辑报告】
标题钩子：{logic_report.get('title_hook', '')}
开头策略：{logic_report.get('opening_3s', '')}
内容结构：{logic_report.get('content_structure', '')}
情绪价值点：{logic_report.get('emotion_points', '')}
SEO关键词：{logic_report.get('seo_keywords', '')}

【任务】
直接输出完整的正文初稿（1500字以上），不要 JSON，不要标题列表，
从正文第一句开始写。要求口语化、有情绪张力、结构完整。
"""
    # yield from：把 chat_stream 产生的每个增量片段逐个转发出去
    yield from chat_stream(
        system_prompt=CONTENT_WRITER_PROMPT,
        user_prompt=user_prompt,
        temperature=0.7,
        max_tokens=4096,
    )
