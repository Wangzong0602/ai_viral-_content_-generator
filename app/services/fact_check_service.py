"""
事实核查服务（方案1）：检测生成内容中的事实断言，联网核对

【背景】
大模型存在"幻觉"：可能虚构人名/事件/数据（如编造"张伟获奖"）。
商用内容发布虚假信息有法律和平台风险，必须在交付用户前预警。

【工作流程】
1. 断言提取：让 AI 找出内容中所有"具体事实断言"
   （真实人名/机构/事件/时间/数据，如"王虹获得菲尔兹奖"）
2. 联网核对：对每个断言联网搜索，判断"有据可依 / 无法核实 / 存疑"
3. 输出风险报告：高风险断言清单 + 整体风险等级

【触发策略】
- 全文核查成本高（每次联网搜索有费用），所以：
  - 仅当题材"疑似涉及真实世界事实"时触发（含人名/获奖/新闻类关键词）
  - 或用户手动要求核查
"""

import json
import re

from app.core.exceptions import BizException
from app.core.logger import logger
from app.services.ai_service import chat, chat_with_search

# 触发核查的"事实敏感"关键词（题材含这些词时自动核查）
FACT_SENSITIVE_KEYWORDS: list[str] = [
    "获", "奖", "夺冠", "第一", "纪录", "发布", "新闻", "宣布",
    "教授", "院士", "科学家", "研究员", "公司", "产品", "数据",
    "统计", "亿", "万", "美元", "元", "%，", "%，", "％",
    # 常见真实人名姓氏（触及时提示人工核实）
    "王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴",
    "徐", "孙", "马", "朱", "胡", "郭", "何", "林", "罗", "高",
]

# 断言提取提示词（第一轮：找事实断言，不开搜索——只做提取）
EXTRACT_CLAIMS_PROMPT = """
你是一位严谨的事实核查员。请从用户提供的文章中，找出所有"可被事实核对的具体断言"：
- 真实人物姓名及其行为/成就（如"王虹获得菲尔兹奖"）
- 具体事件及时间（如"2026年7月大会"）
- 机构/公司及其业务事实
- 具体数据/统计（如"增长50%"）

忽略观点、感受、建议、修辞（如"太震撼了"）。

【输出格式】
必须严格按照 JSON 输出：
{
  "claims": [
    {"text": "断言原文", "type": "人名成就/事件/数据/机构"},
    ...
  ]
}
没有可核对的断言时输出 {"claims": []}
"""

# 单条断言核查提示词（联网搜索核对）
VERIFY_CLAIM_PROMPT = """
你是事实核查员。请基于搜索结果判断以下断言是否属实。

【断言】{claim}

【判断标准】
- 属实：搜索结果支持该断言 → "supported"
- 存疑/无法证实：搜索无结果或信息矛盾 → "unverified"
- 明显错误：搜索明确反对该断言 → "contradicted"

【输出格式】
必须严格按照 JSON 输出：
{{
  "status": "supported|unverified|contradicted",
  "evidence": "简要说明搜索结果依据（30字内）"
}}
"""


def is_fact_sensitive(text: str) -> bool:
    """
    判断题材是否"疑似涉及真实世界事实"（触发自动核查）。

    :param text: 用户输入的关键词/选题
    :return: True=需要核查
    """
    for kw in FACT_SENSITIVE_KEYWORDS:
        if kw in text:
            return True
    return False


def extract_claims(content: str) -> list[dict]:
    """
    提取内容中的事实断言（第一步，不联网，只提取）。

    【为什么用 qwen-plus 而不用默认模型（deepseek-v4-flash）？】
    实测 deepseek-v4-flash 对长文本 + JSON 输出要求会返回空（模型缺陷），
    而 qwen-plus 稳定可靠。事实核查场景必须用 qwen-plus。

    :param content: 待核查的文章
    :return: [{"text": ..., "type": ...}, ...]
    """
    from app.agents.base import extract_json

    text = chat(
        system_prompt=EXTRACT_CLAIMS_PROMPT,
        user_prompt=f"【文章内容】\n{content[:4000]}",
        temperature=0.1,
        max_tokens=1024,
        model="qwen-plus",  # 关键：用可靠模型
    )
    if not text or not text.strip():
        return []
    data = extract_json(text)
    claims = data.get("claims", [])
    # 过滤有效断言
    return [c for c in claims if isinstance(c, dict) and c.get("text")][:10]


def verify_claim(claim_text: str) -> dict:
    """
    联网核查单条断言（第二步）。

    :param claim_text: 断言文本
    :return: {"status": "supported|unverified|contradicted", "evidence": str}
    """
    from app.agents.base import extract_json

    try:
        result = chat_with_search(
            user_prompt=VERIFY_CLAIM_PROMPT.format(claim=claim_text),
            system_prompt="你是严谨的事实核查员，请联网搜索后判断断言真伪。",
            temperature=0.1,
            max_tokens=600,
        )
        # 空结果兜底
        if not result or not result.strip():
            return {"status": "unverified", "evidence": "核查无返回"}

        data = extract_json(result)
        status = data.get("status", "unverified")
        # 解析失败时的兜底：从文本里直接找状态关键词
        if not status or status not in ("supported", "unverified", "contradicted"):
            lower = (result or "").lower()
            if "contradicted" in lower or "不属实" in result or "错误" in result:
                status = "contradicted"
            elif "supported" in lower or "属实" in result:
                status = "supported"
            else:
                status = "unverified"
        return {"status": status, "evidence": data.get("evidence", "")[:60]}
    except Exception as exc:
        logger.warning("断言核查失败 claim=%s: %s", claim_text, exc)
        return {"status": "unverified", "evidence": "核查失败"}


async def fact_check(content: str) -> dict:
    """
    完整事实核查流程（提取断言 → 联网核对）。

    :param content: 生成的文章
    :return: 核查报告：
        {
          "checked": bool,          # 是否执行了核查
          "risk_level": "low|medium|high",
          "claims": [{"text", "type", "status", "evidence"}],
          "warning": str             # 前端展示的警告文案
        }
    """
    # ---------- 1. 提取断言 ----------
    claims = extract_claims(content)
    if not claims:
        return {
            "checked": True,
            "risk_level": "low",
            "claims": [],
            "warning": "未检测到需要核查的事实断言",
        }

    # ---------- 2. 逐个联网核查（串行，控制成本；最多核 5 条） ----------
    results = []
    for claim in claims[:5]:
        result = verify_claim(claim["text"])
        results.append({**claim, **result})

    # ---------- 3. 汇总风险等级 ----------
    contradicted = [r for r in results if r["status"] == "contradicted"]
    unverified = [r for r in results if r["status"] == "unverified"]
    supported = [r for r in results if r["status"] == "supported"]

    if contradicted:
        risk_level = "high"
    elif len(unverified) > 0:
        risk_level = "medium"
    else:
        risk_level = "low"

    # 前端警告文案
    if risk_level == "high":
        warning = f"⚠️ 检测到 {len(contradicted)} 处与事实不符的表述，发布前必须人工核实！"
    elif risk_level == "medium":
        warning = f"⚠️ 有 {len(unverified)} 处事实表述无法通过联网核实，发布前建议人工确认。"
    else:
        warning = f"✅ 已联网核查 {len(supported)} 处事实表述，未发现问题。"

    logger.info(
        "事实核查完成: 断言%d 支持%d 存疑%d 矛盾%d 风险=%s",
        len(results), len(supported), len(unverified), len(contradicted), risk_level,
    )
    return {
        "checked": True,
        "risk_level": risk_level,
        "claims": results,
        "warning": warning,
    }
