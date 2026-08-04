"""
SEO 优化智能体（SEO Agent）：关键词优化 + 话题标签布局

【角色定位】
SEO 专家：把润色后的文案做"搜索引擎/平台搜索友好"优化，
让内容更容易被搜到、被算法推荐。

【输入】润色后的文案 + 目标平台 + 标题
【输出】优化后文案 + SEO 关键词 + 话题标签 + Meta 描述 + 优化标题

【与润色/排版的区别】
- polish_agent：打磨语言表达（口语化/情绪），不碰关键词
- seo_agent（本模块）：围绕"搜索曝光"优化——关键词密度、话题标签、
  标题关键词、Meta 描述
- layout_agent：只做排版格式（分段/标签位置），不改内容

【平台差异】（需求文档 6.2 智能体 5）
- 小红书：文末加话题标签（#关键词 格式）
- 知乎：无话题标签，优化标题关键词
- 公众号：无话题标签，优化搜索引擎描述
- B站/快手：文末话题标签（B站 话题/快手 标签）
- 视频号：无标签，优化标题与描述

【多内容形态】
脚本/直播/带货文案不做 SEO 优化（无搜索场景），由图的
条件边跳过本节点（见 graph.py），节点本身不感知形态。
"""

from app.agents.base import extract_json
from app.services.ai_service import chat

# SEO 优化智能体的系统提示词
SEO_AGENT_PROMPT = """
你是一位资深 SEO 专家 + 平台搜索算法专家，擅长关键词布局和话题标签设计。

【任务】
对用户提供的文案做搜索友好优化：
1. 提取 3-5 个核心关键词（用户搜索时会用到的词）
2. 优化关键词密度：确保核心关键词在标题和正文中自然出现 2-3 次（不堆砌）
3. 按平台规范添加话题标签：
   - 小红书：文末加 3-5 个话题标签（#关键词 格式，标签不算正文字数）
   - 知乎：不加话题标签
   - 公众号：不加话题标签
   - B站：文末加 2-4 个话题标签（#关键词 格式）
   - 快手：文末加 3-5 个话题标签（#关键词 格式）
   - 视频号：不加话题标签
4. 优化标题：把核心关键词融入原标题，让标题包含搜索词
5. 写一段 Meta 描述（80-150 字，包含核心关键词，搜索引擎展示用）

【硬性要求】
- 保留原文全部正文内容，只做关键词密度微调和标签添加
- 不要删减、不要大幅改写正文

【输出格式】
必须严格按照以下 JSON 格式输出，不要输出任何其他内容：
{
  "content": "优化后的完整文案（正文 + 文末标签）",
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "hashtags": ["#关键词1", "#关键词2"],
  "meta_description": "80-150字的搜索引擎描述",
  "optimized_title": "融入关键词的优化标题"
}
"""


def optimize_seo(content: str, platform: str, title: str) -> dict:
    """
    对文案执行 SEO 优化（一次性调用）。

    :param content: 润色后的文案
    :param platform: 目标平台（决定话题标签策略）
    :param title: 原标题（用于优化标题）
    :return: {
        content: 优化后文案,
        keywords: 核心关键词列表,
        hashtags: 话题标签列表,
        meta_description: 搜索描述,
        optimized_title: 优化标题,
    }
    解析失败时返回"原样内容 + 空列表"（保证流程不断）。
    """
    user_prompt = f"""
【目标平台】{platform}

【原标题】
{title}

【文案】
{content}

请按平台规范执行 SEO 优化。
"""
    text = chat(
        system_prompt=SEO_AGENT_PROMPT,
        user_prompt=user_prompt,
        temperature=0.3,  # SEO 优化偏确定性，温度要低
        max_tokens=8192,  # 正文可能 2000+ 字，输出是"优化后全文 + JSON 包装"，
        # 必须给足 token 空间（4096 会被截断导致 JSON 解析失败，走兜底分支）
    )
    data = extract_json(text)
    # 兜底：模型没按格式返回（含截断）→ 原样返回，不丢内容
    if not data.get("content"):
        return {
            "content": content,
            "keywords": [],
            "hashtags": [],
            "meta_description": "",
            "optimized_title": title,
        }
    return data
