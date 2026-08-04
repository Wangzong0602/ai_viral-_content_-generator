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

# 文案创作智能体的系统提示词（图文爆文，默认形态）
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

# 各内容形态的创作提示词（P3 扩展：多内容形态）
# 每个形态定义"正文结构 + 产出要求"，替换默认的图文提示词
CONTENT_TYPE_PROMPTS = {
    "video_script": """
你是一位资深短视频编导，擅长写爆款口播脚本（抖音/小红书视频/视频号通用）。

【写作要求】
- 开场（0-5秒）：钩子话术，一句话抓住观众（悬念/痛点/反差/数字）
- 中间：内容主体（信息密度高，每 15-20 秒一个信息点）
- 结尾：行动召唤（关注/评论/转发引导）+ 金句收尾
- 口语化，适合朗读，多用短句，避免书面语

【输出格式】
必须严格按照以下 JSON 格式输出，不要输出任何其他内容：
{
  "titles": ["标题1", "标题2", "标题3"],
  "content": "完整口播稿（800-1500字，按『开场钩子/主体/结尾』分段，每段标注时长建议，如【开场 0-5秒】）"
}
""",
    "live_script": """
你是一位资深直播带货策划，擅长写高转化直播讲解文案。

【写作要求】
- 开场：30秒留人话术（利益点预告 + 制造期待）
- 产品讲解：3-5 个卖点，每个卖点用『功能-好处-场景』结构展开
- 互动环节：设计 2-3 个互动话术（扣数字/回答问题/引导关注）
- 逼单环节：限时优惠/库存紧张/行动召唤
- 语言口语化、有感染力，多用反问句和感叹句

【输出格式】
必须严格按照以下 JSON 格式输出，不要输出任何其他内容：
{
  "titles": ["标题1", "标题2", "标题3"],
  "content": "完整直播文案（1200-2000字，按『开场留人/产品讲解/互动环节/逼单成交』四段，每段标注时间建议）"
}
""",
    "ecommerce": """
你是一位资深电商文案写手，擅长写高转化商品详情/种草文案。

【写作要求】
- 开头：痛点共鸣（目标用户正在经历的痛苦场景）
- 卖点展开：3-5 个核心卖点，用 FAB 结构（功能-优势-利益）逐条展开
- 信任背书：数据佐证/口碑/场景化证明
- 价格锚点：对比原价/竞品，突出性价比
- 行动召唤：限时优惠 + 下单引导
- 语言口语化、有购买冲动引导力

【输出格式】
必须严格按照以下 JSON 格式输出，不要输出任何其他内容：
{
  "titles": ["标题1", "标题2", "标题3"],
  "content": "完整带货文案（1000-1800字，按『痛点/卖点/信任/价格/行动』结构分段）"
}
""",
}


def _get_writer_prompt(content_type: str) -> str:
    """
    按内容形态选择创作提示词（未知形态回退默认图文提示词，保证流程不断）。
    """
    return CONTENT_TYPE_PROMPTS.get(content_type, CONTENT_WRITER_PROMPT)


def _build_user_prompt(
    topic: dict, logic_report: dict, platform: str, content_type: str = "article"
) -> str:
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

请基于以上策略生成 3 个备选标题和完整{content_type}内容。
"""


def generate_draft(
    topic: dict, logic_report: dict, platform: str, content_type: str = "article"
) -> dict:
    """
    一次性生成文案初稿（非流式）。

    :return: {"titles": [...], "content": "..."}
    """
    text = chat(
        system_prompt=_get_writer_prompt(content_type),
        user_prompt=_build_user_prompt(topic, logic_report, platform, content_type),
        temperature=0.7,
        max_tokens=4096,
    )
    data = extract_json(text)
    # 兜底：如果模型没按格式返回，把整段文本当作正文
    if not data.get("content"):
        data = {"titles": [topic.get("title", "")], "content": text}
    return data


def stream_draft(
    topic: dict, logic_report: dict, platform: str, content_type: str = "article"
):
    """
    流式生成文案初稿（SSE 使用）。

    【返回的是什么？】
    生成器对象，逐个产出"增量文本片段"。调用方（SSE 接口）拿到后
    一段段推送给前端，前端逐字渲染。

    注意：流式模式无法等到完整 JSON 再解析，
    所以这里不要求模型输出 JSON，直接让它输出"纯正文文本"，
    标题交给前一步的选题标题兜底（保证流程简单可靠）。

    【多形态支持】
    content_type 决定创作提示词（视频脚本/直播文案/电商带货），
    输出结构也随之变化（分镜/分段/卖点结构）。
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
        system_prompt=_get_writer_prompt(content_type),
        user_prompt=user_prompt,
        temperature=0.7,
        max_tokens=4096,
    )
