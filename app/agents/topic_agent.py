"""
选题智能体（Topic Agent）：生成爆款选题方向

【角色定位】
资深自媒体选题策划师：擅长捕捉"热点 + 用户需求 + 平台趋势"的交集。

【输入】用户输入的关键词/领域 + 目标平台
【输出】5 个选题方向（每个含：标题、简介、目标人群、预期效果）
【调用方式】一次性调用（选题列表不长，无需流式）

【提示词设计要点】
提示词 = 角色设定 + 任务规则 + 输出格式约定。
写提示词的经验：
1. 角色越具体，输出越专业（"拥有10年内容运营经验"比"你是助手"好）
2. 输出格式要约定明确（JSON 结构），方便程序解析
3. 给出判断标准（标题要悬念/反转/数字/情绪），引导模型思考方向
"""

from app.agents.base import extract_json
from app.services.ai_service import chat

# 选题智能体的系统提示词（角色 + 规则）
TOPIC_AGENT_PROMPT = """
你是一位资深的自媒体选题策划师，拥有 10 年以上的内容运营经验。
你擅长捕捉"热点 + 用户需求 + 平台趋势"的交集，生成爆款选题。

【平台推荐机制】
- 小红书：优先推荐「高完播率 + 高收藏率」的内容
- 知乎：优先推荐「高停留时长 + 高点赞率」的内容
- 公众号：优先推荐「高打开率 + 高转发率」的内容

【选题标准】
- 标题要吸引眼球（悬念、反转、数字、情绪）
- 简介要简洁明了（50 字内）
- 目标人群要精准（谁会看）
- 预期效果要可量化（阅读量、涨粉量）

【输出格式】
必须严格按照以下 JSON 格式输出，不要输出任何其他内容：
{
  "topics": [
    {
      "title": "选题标题",
      "summary": "选题简介（50字内）",
      "target_audience": "目标人群",
      "expected_effect": "预期效果"
    }
  ]
}
"""


def generate_topics(keyword: str, platform: str, template_structure: str = "") -> list[dict]:
    """
    生成 5 个爆款选题方向。

    :param keyword: 用户输入的关键词/领域（如"AI工具""健康养生"）
    :param platform: 目标平台（小红书/公众号/知乎）
    :param template_structure: 内容模板结构要求（可选，注入提示词让选题贴合模板）
    :return: 选题列表，格式：
        [{"title": "...", "summary": "...", "target_audience": "...", "expected_effect": "..."}]
        解析失败时返回空列表（调用方展示兜底文案）
    """
    # 模板结构注入（用户选了模板时生效）
    template_part = ""
    if template_structure:
        template_part = f"""
【用户选择的模板结构要求】（选题需适合该模板）
{template_structure}
"""

    # 组装用户提示词：把变量嵌入模板（{keyword}、{platform} 会被替换）
    user_prompt = f"""
【用户输入】
- 关键词：{keyword}
- 目标平台：{platform}
{template_part}
请生成 5 个爆款选题方向。
"""
    # 调用大模型（temperature=0.8：选题需要创意，温度稍高更有发散性）
    text = chat(
        system_prompt=TOPIC_AGENT_PROMPT,
        user_prompt=user_prompt,
        temperature=0.8,
    )
    # 清洗模型输出为 JSON，取 topics 字段；解析失败给空列表
    data = extract_json(text)
    return data.get("topics", [])
