"""
个人数据看板统计服务：聚合查询用户的创作数据

【统计口径】
- 只统计"已完成"（status=2）的创作任务
- 删除的（status=3）、失败的（status=3 也是失败，见 creation_task 状态机）排除
  注意：creation_task 的 status 含义：
  0=排队中 1=生成中 2=已完成 3=失败/已删除
  所以统计"已发布成果"只用 status=2；"尝试次数"用全部（除排队中）

【输出维度】
1. 概览：总创作数、总字数、平均质量分、节省时间（每篇按 2 小时估算）
2. 趋势：近 N 天每日创作数量（折线图）
3. 平台分布：各平台创作数量（饼图）
4. 质量分布：质量分区间分布（柱状图）
"""

from datetime import date, datetime, timedelta

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models.creation_task import CreationTask

# 每篇创作节省的时间（小时）—— 对比人工 4-6 小时的保守估算
HOURS_SAVED_PER_ARTICLE = 2.0


def get_overview(db: Session, user_id: int, days: int = 30) -> dict:
    """
    获取用户数据看板全部统计。

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param days: 趋势统计的天数（近 N 天，默认 30）
    :return: 统计字典（结构见 docstring）
    """
    # ---------- 1. 概览统计（已完成的任务） ----------
    total_count = db.scalar(
        select(func.count())
        .select_from(CreationTask)
        .where(CreationTask.user_id == user_id, CreationTask.status == 2)
    ) or 0

    total_chars = db.scalar(
        select(func.coalesce(func.sum(func.char_length(CreationTask.content)), 0))
        .where(CreationTask.user_id == user_id, CreationTask.status == 2)
    ) or 0

    avg_quality = db.scalar(
        select(func.avg(CreationTask.quality_score))
        .where(CreationTask.user_id == user_id, CreationTask.status == 2)
    ) or 0

    # 尝试总数（含失败）与失败数（status=3 且有关键词非空 = 失败；软删除的记录 keyword 也在，
    # 这里简化：失败 = status=3 且 completed_at 为空？不准确。
    # 更可靠：失败记录 error_message 非空。软删除 status=3 且 error_message 为空。
    failed_count = db.scalar(
        select(func.count())
        .select_from(CreationTask)
        .where(
            CreationTask.user_id == user_id,
            CreationTask.status == 3,
            CreationTask.error_message != "",
        )
    ) or 0

    # ---------- 2. 近 N 天创作趋势 ----------
    since = datetime.now() - timedelta(days=days - 1)
    since_date = since.date()  # 只看日期部分
    rows = db.execute(
        select(
            func.date(CreationTask.created_at).label("d"),
            func.count().label("cnt"),
        )
        .where(
            CreationTask.user_id == user_id,
            CreationTask.status == 2,
            CreationTask.created_at >= since,
        )
        .group_by(func.date(CreationTask.created_at))
    ).all()
    count_by_date = {r.d: r.cnt for r in rows}

    # 补全缺失日期（无创作的日期填 0，保证折线图连续）
    trend: list[dict] = []
    for i in range(days):
        day = since_date + timedelta(days=i)
        trend.append({"date": day.isoformat(), "count": count_by_date.get(day, 0)})

    # ---------- 3. 平台分布 ----------
    platform_rows = db.execute(
        select(CreationTask.platform, func.count().label("cnt"))
        .where(CreationTask.user_id == user_id, CreationTask.status == 2)
        .group_by(CreationTask.platform)
    ).all()
    platforms = [
        {"platform": r.platform or "未知", "count": r.cnt} for r in platform_rows
    ]

    # ---------- 4. 质量分布（分段统计，区间互斥） ----------
    quality_rows = db.execute(
        select(
            func.sum(case((CreationTask.quality_score >= 90, 1), else_=0)).label("q90"),
            func.sum(
                case(
                    (
                        and_(
                            CreationTask.quality_score >= 70,
                            CreationTask.quality_score < 90,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("q70_90"),
            func.sum(
                case(
                    (
                        and_(
                            CreationTask.quality_score >= 60,
                            CreationTask.quality_score < 70,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("q60_70"),
            func.sum(
                case((CreationTask.quality_score < 60, 1), else_=0)
            ).label("q_below"),
        ).where(CreationTask.user_id == user_id, CreationTask.status == 2)
    ).one()

    quality_dist = [
        {"range": "90+", "count": int(quality_rows.q90 or 0)},
        {"range": "70-89", "count": int(quality_rows.q70_90 or 0)},
        {"range": "60-69", "count": int(quality_rows.q60_70 or 0)},
        {"range": "<60", "count": int(quality_rows.q_below or 0)},
    ]

    return {
        "summary": {
            "total_count": int(total_count),
            "total_chars": int(total_chars),
            "avg_quality": round(float(avg_quality), 1),
            "failed_count": int(failed_count),
            "saved_hours": round(total_count * HOURS_SAVED_PER_ARTICLE, 1),
        },
        "trend": trend,
        "platforms": platforms,
        "quality_dist": quality_dist,
    }
