"""
爆文逻辑分析智能体（Viral Logic Analyzer）：拆解爆文要素

【角色定位】
平台算法专家 + 用户心理学家：深度理解平台推荐机制和用户心理。

【输入】用户选择的选题 + 目标平台
【输出】爆文逻辑报告：标题钩子、开头3秒、内容结构、情绪价值点、SEO关键词

【为什么要这一步？】
这是整个平台的"技术含金量"所在：
普通 AI 写作是"直接生成文章"，本平台是先分析"这篇文章为什么能火"，
再带着策略去写。生成的内容就有结构、有钩子、有情绪设计，
而不是平铺直叙的流水账。
"""

from app.agents.base import extract_json
from app.services.ai_service import chat

# 爆文逻辑分析智能体的系统提示词
LOGIC_ANALYZER_PROMPT = """
你是一位平台算法专家 + 用户心理学家，深度理解各大内容平台的推荐机制和用户心理。

【平台推荐机制库】
- 小红书：优先推荐「高完播率 + 高收藏率」的内容
- 知乎：优先推荐「高停留时长 + 高点赞率 + 高评论质量」的内容
- 公众号：优先推荐「高打开率 + 高转发率 + 高在看率」的内容

【你的任务】
1. 分析该平台的推荐机制
2. 拆解爆文要素：
   - 标题钩子设计（悬念、反转、数字、情绪）
   - 开头 3 秒设计（抓住注意力）
   - 内容结构设计（痛点 → 爽点 → 行动召唤）
   - 情绪价值点（共鸣、焦虑、好奇、愤怒）
   - SEO 关键词布局
3. 输出爆文逻辑报告

【输出格式】
必须严格按照以下 JSON 格式输出，不要输出任何其他内容：
{
  "title_hook": {
    "strategy": "标题钩子策略（如：数字+悬念）",
    "example": "一个具体的示例标题"
  },
  "opening_3s": {
    "strategy": "开头策略（如：痛点共鸣+方案预告）",
    "example": "一个具体的示例开头（50字内）"
  },
  "content_structure": {
    "part1": "第一部分安排（如：痛点描述引发共鸣）",
    "part2": "第二部分安排（如：解决方案详细展开）",
    "part3": "第三部分安排（如：行动召唤互动引导）"
  },
  "emotion_points": ["情绪点1", "情绪点2", "情绪点3"],
  "seo_keywords": ["关键词1", "关键词2", "关键词3"]
}
"""


def analyze_logic(topic: dict, platform: str) -> dict:
    """
    分析爆文逻辑，输出创作策略报告。

    :param topic: 用户选择的选题（含 title/summary/target_audience）
    :param platform: 目标平台
    :return: 爆文逻辑报告字典（含 title_hook/opening_3s/content_structure/emotion_points/seo_keywords）
    """
    user_prompt = f"""
【用户选题】
- 标题：{topic.get('title', '')}
- 简介：{topic.get('summary', '')}
- 目标平台：{platform}

请拆解这个选题的爆文逻辑，输出创作策略报告。
"""
    text = chat(
        system_prompt=LOGIC_ANALYZER_PROMPT,
        user_prompt=user_prompt,
        temperature=0.6,  # 分析需要严谨，温度低一点
    )
    return extract_json(text)
