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
]


def init_seed_templates(db: Session) -> None:
    """
    初始化种子模板数据（幂等：表空时才插入）。

    在应用启动时调用（见 main.py lifespan）。
    """
    count = db.scalar(select(ContentTemplate.id).limit(1))
    if count is not None:
        return  # 已有数据，跳过
    for t in SEED_TEMPLATES:
        db.add(ContentTemplate(**t))
    db.commit()
    logger.info("内容模板种子数据已初始化: %d 个模板", len(SEED_TEMPLATES))


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
