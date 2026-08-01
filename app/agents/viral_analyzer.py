"""
爆文逆向分析智能体（Viral Analyst）：拆解一篇爆文为什么能火

【角色定位】
平台算法专家 + 内容策略分析师：像"解剖"一样拆解爆文的可复制要素。

【分析维度】（与创作智能体的爆文逻辑分析对应，形成闭环）
1. 标题钩子：用了什么钩子策略（悬念/数字/反转/情绪）
2. 开头 3 秒：如何抓住注意力
3. 内容结构：痛点→爽点→行动召唤 的节奏安排
4. 情绪价值点：共鸣/焦虑/好奇/愤怒等
5. 行动召唤：如何引导点赞/收藏/评论
6. SEO 关键词：布局了哪些关键词

【为什么有价值？】
- 对用户：看到一篇 10 万+ 爆文，想知道"为什么能火"——学到可复用的方法论
- 与创作模块闭环：创作时生成"爆文逻辑报告"，逆向分析拆解别人的爆文，
  两者结构一致，用户可以把分析结果直接用于下一次创作
"""

from app.agents.base import extract_json
from app.services.ai_service import chat

# 逆向分析的系统提示词
ANALYZER_PROMPT = """
你是一位资深的内容策略分析师，擅长拆解爆款文章的可复制要素。
请分析用户提供的文章，输出一份专业的爆文拆解报告。

【分析维度】
1. title_hook（标题钩子）：标题用了什么策略（悬念/数字/反转/情绪/对比），具体怎么体现
2. opening_3s（开头3秒）：开头如何抓住读者注意力，用了什么技巧
3. content_structure（内容结构）：整体结构如何安排（痛点→爽点→行动召唤 的节奏），分几部分
4. emotion_points（情绪价值）：文章调动了哪些情绪（共鸣/焦虑/好奇/愤怒/爽感），分别在哪个位置
5. cta（行动召唤）：结尾如何引导互动（点赞/收藏/评论/关注），用了什么话术
6. seo_keywords（SEO关键词）：核心关键词是什么，密度和位置如何

【输出格式】
必须严格按照以下 JSON 格式输出，不要输出任何其他内容：
{
  "title_hook": "标题钩子分析",
  "opening_3s": "开头3秒分析",
  "content_structure": "内容结构分析",
  "emotion_points": "情绪价值分析",
  "cta": "行动召唤分析",
  "seo_keywords": "SEO关键词分析",
  "overall": "总体评价与可复用的方法论总结"
}
"""


def analyze_article(content: str, title: str = "") -> dict:
    """
    逆向分析一篇爆文。

    :param content: 文章正文
    :param title: 文章标题（可选，有标题时分析更准确）
    :return: 分析报告字典：
        {title_hook, opening_3s, content_structure, emotion_points, cta, seo_keywords, overall}
        解析失败时返回空字典
    """
    # 内容截断：防止超长输入（模型有 token 限制）
    trimmed = content[:8000]

    title_part = f"\n【文章标题】{title}" if title else ""
    user_prompt = f"{title_part}\n【文章内容】\n{trimmed}\n\n请拆解这篇爆文的可复制要素。"

    # 分析需要深度思考，温度偏低（0.3）保证输出质量稳定
    text = chat(
        system_prompt=ANALYZER_PROMPT,
        user_prompt=user_prompt,
        temperature=0.3,
        max_tokens=2048,
    )
    return extract_json(text)
