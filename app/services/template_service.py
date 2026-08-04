"""
内容模板服务：模板列表查询 + 种子数据初始化

【种子模板设计】（各平台常见爆款结构）
- 小红书：痛点共鸣型 / 清单盘点型 / 教程步骤型
- 公众号：观点输出型 / 故事叙述型 / 深度干货型
- 知乎：结论前置型 / 经历分享型 / 专业论证型
"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.models.content_template import ContentTemplate

# 种子模板数据（structure 为 JSON 字符串）
SEED_TEMPLATES: list[dict] = [
    # ---------- 小红书 ----------
    {
        "name": "痛点共鸣型",
        "platform": "小红书",
        "description": "开头戳中用户痛点引发共鸣，中间给干货解决方案，结尾引导互动",
        "structure": json.dumps(
            {
                "hook": "数字 + 痛点（如'3个方法'）",
                "opening": "直接说出读者正在经历的痛苦场景，引发共鸣",
                "body": "分点给出解决方案，每点一个场景化小标题",
                "cta": "引导收藏 + 评论区分享自己的经历",
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "清单盘点型",
        "platform": "小红书",
        "description": "以'N个xxx'清单形式盘点，信息密度高、易收藏",
        "structure": json.dumps(
            {
                "hook": "数字清单（如'5款''8个'）",
                "opening": "一句话说明这份清单的价值",
                "body": "逐条列出，每条带简短说明和适用场景",
                "cta": "引导收藏 + 关注获取后续清单",
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "教程步骤型",
        "platform": "小红书",
        "description": "保姆级步骤教程，强调可操作性",
        "structure": json.dumps(
            {
                "hook": "效果承诺（如'手把手教你'）",
                "opening": "展示最终效果引发期待",
                "body": "分步骤讲解，每步有具体操作和注意事项",
                "cta": "引导收藏 + 评论区提问答疑",
            },
            ensure_ascii=False,
        ),
    },
    # ---------- 公众号 ----------
    {
        "name": "观点输出型",
        "platform": "公众号",
        "description": "开篇抛出鲜明观点，层层论证，结尾升华",
        "structure": json.dumps(
            {
                "hook": "反常识观点或金句",
                "opening": "直接抛出核心观点，制造认知冲突",
                "body": "3-4 个分论点，每个配案例和数据论证",
                "cta": "引导在看 + 留言讨论观点",
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "故事叙述型",
        "platform": "公众号",
        "description": "用真实故事引入，情节带动情绪，最后升华主题",
        "structure": json.dumps(
            {
                "hook": "故事悬念（'我认识一个朋友...'）",
                "opening": "讲述一个真实故事开头，设置悬念",
                "body": "故事发展 - 转折 - 结果，穿插感悟",
                "cta": "引导转发 + 评论区分享类似经历",
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "深度干货型",
        "platform": "公众号",
        "description": "系统化方法论输出，结构严谨，适合知识类",
        "structure": json.dumps(
            {
                "hook": "方法论承诺（'一套完整体系'）",
                "opening": "说明问题背景和本文价值",
                "body": "系统分章：概念 - 方法 - 案例 - 常见误区",
                "cta": "引导收藏 + 关注持续输出",
            },
            ensure_ascii=False,
        ),
    },
    # ---------- 知乎 ----------
    {
        "name": "结论前置型",
        "platform": "知乎",
        "description": "第一句直接给答案，再展开论证，符合知乎阅读习惯",
        "structure": json.dumps(
            {
                "hook": "直接结论（'答案是：...'）",
                "opening": "第一句直接给出核心结论",
                "body": "分点论证，每点有理有据，可补充数据",
                "cta": "引导点赞 + 评论区补充讨论",
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "经历分享型",
        "platform": "知乎",
        "description": "个人真实经历分享，可信度高，容易引发共鸣",
        "structure": json.dumps(
            {
                "hook": "身份 + 经历标签",
                "opening": "自我介绍 + 引出经历背景",
                "body": "时间线叙述经历，穿插教训和反思",
                "cta": "引导点赞 + 评论区交流",
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "专业论证型",
        "platform": "知乎",
        "description": "严肃专业论证，引用数据文献，建立专业权威",
        "structure": json.dumps(
            {
                "hook": "问题重述 + 专业视角",
                "opening": "界定问题范围，表明专业立场",
                "body": "论点 - 论据 - 论证，引用数据或权威来源",
                "cta": "引导关注 + 专业讨论",
            },
            ensure_ascii=False,
        ),
    },
    # ---------- B站（P3 扩展：深度测评/硬核科普/热点解读） ----------
    {
        "name": "深度测评型",
        "platform": "B站",
        "description": "客观深度测评，优劣都讲，建立专业可信度（三连友好）",
        "structure": json.dumps(
            {
                "hook": "反差开场（'先说结论：值不值得买'）",
                "opening": "直接给结论 + 使用场景说明",
                "body": "分维度测评（外观/性能/价格/槽点），每点配实测数据",
                "cta": "引导一键三连 + 评论区答疑",
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "硬核科普型",
        "platform": "B站",
        "description": "用通俗语言讲清专业原理，层层递进，适合知识区",
        "structure": json.dumps(
            {
                "hook": "好奇问题（'为什么...'）",
                "opening": "抛出反常识现象引发好奇",
                "body": "从现象到原理逐步拆解，善用类比，配示意图描述",
                "cta": "引导收藏 + 三连支持继续更新",
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "热点解读型",
        "platform": "B站",
        "description": "蹭热点话题做深度解读，信息增量 + 观点输出",
        "structure": json.dumps(
            {
                "hook": "热点事件开场（'最近爆火的...'）",
                "opening": "简述热点事件 + 点出公众关注点",
                "body": "事件全貌 - 深层分析 - 个人观点，补充独家信息",
                "cta": "引导弹幕讨论 + 三连",
            },
            ensure_ascii=False,
        ),
    },
    # ---------- 快手（P3 扩展：老铁故事/实用技能/真实体验） ----------
    {
        "name": "老铁故事型",
        "platform": "快手",
        "description": "真实生活故事，接地气真诚，拉近老铁距离",
        "structure": json.dumps(
            {
                "hook": "真实场景开头（'今天遇到件事...'）",
                "opening": "直接从生活场景切入，像唠家常",
                "body": "故事展开 - 转折 - 感悟，穿插口语表达",
                "cta": "引导评论互动 + 关注",
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "实用技能型",
        "platform": "快手",
        "description": "快速上手的生活技能，简单直接不废话",
        "structure": json.dumps(
            {
                "hook": "结果承诺（'学会这个省下...'）",
                "opening": "一句话说明能解决什么问题",
                "body": "分步骤演示，每步一句话，突出关键点",
                "cta": "引导收藏 + 关注学更多",
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "真实体验型",
        "platform": "快手",
        "description": "亲身经历的真实体验分享，朴素可信",
        "structure": json.dumps(
            {
                "hook": "亲身经历开场（'我试了一个月...'）",
                "opening": "交代体验背景和初衷",
                "body": "过程如实叙述，好与不好都说，不吹不黑",
                "cta": "引导评论区交流真实感受",
            },
            ensure_ascii=False,
        ),
    },
    # ---------- 视频号（P3 扩展：观点分享/情感共鸣/实用干货） ----------
    {
        "name": "观点分享型",
        "platform": "视频号",
        "description": "鲜明观点 + 社交化表达，适合朋友圈传播",
        "structure": json.dumps(
            {
                "hook": "金句开场（'真正厉害的人...'）",
                "opening": "抛出观点金句，适合截图转发",
                "body": "分点论证，每点短小精悍，金句收尾",
                "cta": "引导点赞 + 转发给需要的人",
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "情感共鸣型",
        "platform": "视频号",
        "description": "戳中用户情感痛点，引发共鸣与转发",
        "structure": json.dumps(
            {
                "hook": "情感场景（'你有没有过这样的时刻...'）",
                "opening": "描述共情场景，拉近距离",
                "body": "故事 + 情绪递进 + 温暖升华",
                "cta": "引导在看 + 转发",
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "实用干货型",
        "platform": "视频号",
        "description": "知识类干货，结构化输出，适合收藏分享",
        "structure": json.dumps(
            {
                "hook": "干货承诺（'整理了3个方法...'）",
                "opening": "说明内容价值和适用人群",
                "body": "结构化清单式输出，重点加粗强调",
                "cta": "引导收藏 + 转发给同事朋友",
            },
            ensure_ascii=False,
        ),
    },
]


def init_seed_templates(db: Session) -> None:
    """
    初始化种子模板数据（幂等：按「平台 + 名称」缺失补插）。

    在应用启动时调用（见 main.py lifespan）。

    【为什么不用"表空才插入"？】
    平台是持续扩展的（P3 新增 B站/快手/视频号），老用户数据库里已有旧模板。
    如果"表空才插入"，新增平台的模板永远不会补上。
    所以改为：逐条检查 (platform, name) 是否已存在，缺失的才补插——
    既不重复插入旧模板，又能自动补上新平台的模板。
    """
    inserted = 0
    for t in SEED_TEMPLATES:
        exists = db.scalar(
            select(ContentTemplate.id).where(
                ContentTemplate.platform == t["platform"],
                ContentTemplate.name == t["name"],
            )
        )
        if exists is not None:
            continue  # 已存在（包括用户可能改过的），跳过
        db.add(ContentTemplate(**t))
        inserted += 1
    if inserted:
        db.commit()
        logger.info("内容模板种子数据已补充: %d 个模板", inserted)


def get_templates(db: Session, platform: str | None = None) -> list[ContentTemplate]:
    """
    查询可用模板列表。

    :param db: 数据库会话
    :param platform: 按平台过滤（可选，None 返回全部）
    """
    stmt = select(ContentTemplate).where(ContentTemplate.is_active == True)  # noqa: E712
    if platform:
        stmt = stmt.where(ContentTemplate.platform == platform)
    stmt = stmt.order_by(ContentTemplate.platform.asc(), ContentTemplate.id.asc())
    return list(db.scalars(stmt))


def get_template(db: Session, template_id: int) -> ContentTemplate | None:
    """按 ID 查询模板（不存在返回 None）。"""
    return db.get(ContentTemplate, template_id)
