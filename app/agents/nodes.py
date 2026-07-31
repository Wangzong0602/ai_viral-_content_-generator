"""
LangGraph 节点函数（企业级）

【什么是节点（Node）？】
节点 = 图中的"一个处理步骤"。每个节点是一个普通函数：
- 输入：当前 State（从上一步继承的所有数据）
- 输出：State 的"局部更新"（只返回自己修改的字段，LangGraph 自动合并）

【企业级节点设计规范】
1. 单一职责：每个节点只做一件事（选题解析/逻辑分析/写作/润色/排版/质检）
2. 流式注入：写作/润色节点通过 StreamWriter 参数把增量文本推给前端
3. 幂等与兜底：模型输出异常时返回安全默认值，不让图崩溃
4. 显式更新 current_step：让调用方（SSE 层）知道当前进度

【StreamWriter 是什么？】
LangGraph 的"自定义流式通道"：
- 节点函数声明 writer: StreamWriter 参数，框架自动注入
- 节点内调用 writer(chunk) 可以把任意数据实时"吐"出图外
- 配合 stream_mode="custom"，调用方逐段收到这些数据
这正是 SSE 实时推送的实现基础（前端打字机效果）。
"""

import json

from langgraph.types import StreamWriter

from app.agents.base import extract_json
from app.agents.logic_analyzer import analyze_logic
from app.agents.layout_agent import layout_content
from app.agents.polish_agent import stream_polish
from app.agents.state import CreationState
from app.agents.topic_agent import generate_topics
from app.services.ai_service import chat_stream
from app.services.sensitive_words import check_sensitive

# 敏感词触发重写时的系统提示词
REVISE_PROMPT = """
你是一位资深文案编辑。用户提供的文案中包含敏感词，可能违反平台规范。
请重写这段文案：
1. 删除或替换所有敏感词（用中性、合规的表达替代）
2. 保持原文的核心观点、结构、情绪不变
3. 保持与原文接近的长度
直接输出重写后的完整文案，不要解释，不要输出 JSON。
"""


# ============================================================
# 节点 1：选题解析（resolve_topic）
# ============================================================
def resolve_topic_node(state: CreationState) -> dict:
    """
    从选题列表中解析出"用户选择的那一个选题"。

    【为什么需要这个节点？】
    用户在前端从 5 个选题里点选一个（selected_title），
    但后续智能体需要完整的选题信息（标题/简介/目标人群/预期效果）。
    所以根据标题精确匹配，取出完整的选题字典。

    【兜底策略】
    标题匹配不上（可能被模型改了字）→ 取列表第一个，保证流程不断。
    """
    selected = state["selected_title"]
    topics = state.get("topics", [])
    # next(生成器, 默认值)：找到第一个标题匹配的选题
    topic = next(
        (t for t in topics if t.get("title") == selected),
        topics[0] if topics else {},  # 匹配失败兜底：第一个选题
    )
    return {"topic": topic, "current_step": "resolve_topic"}


# ============================================================
# 节点 2：爆文逻辑分析（logic_analyzer）
# ============================================================
def logic_analyzer_node(state: CreationState) -> dict:
    """
    分析爆文逻辑（标题钩子/开头3秒/内容结构/情绪点/SEO关键词）。

    调用大模型时如果出现网络类异常，LangGraph 的 RetryPolicy
    （见 state.py 的 NODE_RETRY_POLICY）会自动指数退避重试，
    节点函数本身无需写重试代码——这是企业级编排框架带来的能力。
    """
    topic = state.get("topic", {})
    platform = state["platform"]
    # analyze_logic 返回字典；解析失败时返回 {}，由下游兜底
    report = analyze_logic(topic, platform)
    return {
        "logic_report": report,
        "current_step": "logic_analyzer",
    }


# ============================================================
# 节点 3：文案创作（content_writer，流式）
# ============================================================
def content_writer_node(state: CreationState, writer: StreamWriter) -> dict:
    """
    生成文案初稿（核心节点，流式输出正文）。

    【流程】
    1. 构造提示词（选题 + 爆文逻辑报告 → 生成正文）
    2. chat_stream 逐段产出增量文本
    3. 每段同时做两件事：
       a. writer(chunk)  → 实时推给前端（SSE 打字机效果）
       b. 拼接进 drafts   → 最终形成完整正文存入 State
    4. 返回 {"draft": 完整正文} 交给下一步润色

    【为什么 draft 要用 JSON 格式输出但流式取 content？】
    MVP 阶段为简化：流式模式直接输出纯正文（不含 JSON 包装），
    标题信息已由选题提供，无需模型再生成（避免流式 JSON 解析复杂度）。
    企业级升级方向：改用 LangChain 结构化输出（with_structured_output），
    流式也能拿到可靠的结构化结果（列入 P1 扩展）。
    """
    topic = state.get("topic", {})
    logic_report = state.get("logic_report", {})
    platform = state["platform"]

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
    # 从 ai_service 导入创作提示词（保持提示词与之前一致）
    from app.agents.content_writer import CONTENT_WRITER_PROMPT

    parts: list[str] = []  # 收集所有增量片段
    for chunk in chat_stream(
        system_prompt=CONTENT_WRITER_PROMPT,
        user_prompt=user_prompt,
        temperature=0.7,
        max_tokens=4096,
    ):
        writer(chunk)  # 实时推送片段给前端
        parts.append(chunk)  # 同时拼接进完整正文
    draft = "".join(parts)
    return {"draft": draft, "current_step": "content_writer"}


# ============================================================
# 节点 4：润色优化（polish_agent，流式）
# ============================================================
def polish_agent_node(state: CreationState, writer: StreamWriter) -> dict:
    """
    润色优化：语言口语化、增强情绪、适配平台风格（流式输出）。

    【兜底策略】润色后如果内容被模型"压缩"得太短（< 原稿 50%），
    说明模型可能误删了内容，此时退回初稿，保证信息量不丢失。
    """
    draft = state.get("draft", "")
    platform = state["platform"]

    parts: list[str] = []
    for chunk in stream_polish(draft, platform):
        writer(chunk)
        parts.append(chunk)
    polished = "".join(parts)

    # 兜底：润色结果异常变短 → 退回初稿
    if len(polished) < len(draft) * 0.5:
        polished = draft
    return {"polished": polished, "current_step": "polish_agent"}


# ============================================================
# 节点 5：排版整合（layout_agent）
# ============================================================
def layout_agent_node(state: CreationState) -> dict:
    """
    按平台风格排版（小红书加话题标签/公众号小标题/知乎结构分层）。
    排版是确定性工作，一次性调用（无需流式）。
    """
    polished = state.get("polished", "")
    platform = state["platform"]
    final_content = layout_content(polished, platform)
    return {"final_content": final_content, "current_step": "layout_agent"}


# ============================================================
# 节点 6：质量审核（quality_checker，含条件路由）
# ============================================================
def quality_checker_node(state: CreationState) -> dict:
    """
    质量审核：敏感词检查 + 评分。

    该节点是"流程分支点"：
    - 干净 → 走 END（流程结束）
    - 有敏感词且重试次数未达上限 → 走 revise（重写）再回来
    - 有敏感词但已达上限 → 放行（记录告警，交给人工/前端提示）
    """
    content = state.get("final_content", "")
    report = check_sensitive(content)

    # 评分逻辑：无敏感词 100 分；有敏感词 60 分（功能可用但需人工处理）
    score = 100 if not report["has_sensitive"] else 60
    return {
        "sensitive_report": report,
        "quality_score": score,
        "current_step": "quality_checker",
    }


# ============================================================
# 节点 7：敏感词重写（revise）
# ============================================================
def revise_node(state: CreationState, writer: StreamWriter) -> dict:
    """
    敏感词重写：质量审核不过时，重写文案以消除敏感词。

    由条件边触发（quality_checker → revise），执行后回到 quality_checker
    再次检查，形成"审核-重写-再审核"的循环，直到通过或达上限。
    """
    content = state.get("final_content", "")
    platform = state["platform"]
    # 把敏感词信息注入提示词，让模型知道要改什么
    report = state.get("sensitive_report", {})
    words = "、".join(report.get("words", []))

    user_prompt = f"""
【目标平台】{platform}
【需要移除的敏感词】{words}

【原文】
{content}

请重写为合规版本。
"""
    parts: list[str] = []
    for chunk in chat_stream(
        system_prompt=REVISE_PROMPT,
        user_prompt=user_prompt,
        temperature=0.5,
        max_tokens=4096,
    ):
        writer(chunk)  # 重写过程也实时推给前端
        parts.append(chunk)
    rewritten = "".join(parts)

    return {
        "final_content": rewritten,
        "retry_count": 1,  # 配合 Annotated[int, operator.add] 累加
        "current_step": "revise",
    }
