"""
后台管理服务：用户管理 / 内容管理 / 全局统计 的查询逻辑
"""

from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.creation_task import CreationTask
from app.models.order import Order
from app.models.user import User


# ---------- 用户管理 ----------

def get_admin_users(
    db: Session,
    keyword: str | None = None,
    limit: int = 50,
) -> list[User]:
    """
    查询用户列表（可按手机号/昵称搜索）。

    :param db: 数据库会话
    :param keyword: 搜索关键词（匹配手机号/昵称/邮箱，可选）
    :param limit: 返回条数上限
    """
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
    if keyword:
        like = f"%{keyword}%"
        stmt = (
            select(User)
            .where(or_(User.phone.like(like), User.nickname.like(like), User.email.like(like)))
            .order_by(User.created_at.desc())
            .limit(limit)
        )
    return list(db.scalars(stmt))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """按 ID 查用户。"""
    return db.get(User, user_id)


def get_user_stats(db: Session, user_id: int) -> tuple[int, int]:
    """
    查询用户创作统计（篇数、总字数）。

    :return: (task_count, char_count)
    """
    task_count = db.scalar(
        select(func.count())
        .select_from(CreationTask)
        .where(CreationTask.user_id == user_id, CreationTask.status == 2)
    ) or 0
    char_count = db.scalar(
        select(func.coalesce(func.sum(func.char_length(CreationTask.content)), 0))
        .where(CreationTask.user_id == user_id, CreationTask.status == 2)
    ) or 0
    return int(task_count), int(char_count)


# ---------- 内容管理 ----------

def get_admin_contents(
    db: Session,
    keyword: str | None = None,
    platform: str | None = None,
    limit: int = 50,
) -> list[CreationTask]:
    """
    查询所有用户的生成记录（可按关键词/平台筛选）。

    :param db: 数据库会话
    :param keyword: 搜索关键词（匹配标题/主题，可选）
    :param platform: 平台筛选（可选）
    :param limit: 返回条数上限
    """
    stmt = select(CreationTask).order_by(CreationTask.created_at.desc()).limit(limit)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(CreationTask.selected_title.like(like), CreationTask.keyword.like(like))
        )
    if platform:
        stmt = stmt.where(CreationTask.platform == platform)
    return list(db.scalars(stmt))


def get_content_by_id(db: Session, content_id: int) -> CreationTask | None:
    """按 ID 查生成记录。"""
    return db.get(CreationTask, content_id)


# ---------- 会员订单管理 ----------

def get_admin_orders(
    db: Session,
    status: int | None = None,
    keyword: str | None = None,
    limit: int = 50,
) -> list[Order]:
    """
    查询所有订单（可按状态/关键词筛选）。

    :param db: 数据库会话
    :param status: 订单状态筛选（1待支付 2已支付 3已取消 4已退款），可选
    :param keyword: 搜索关键词（匹配订单号/套餐名），可选
    :param limit: 返回条数上限
    """
    stmt = select(Order).order_by(Order.created_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(Order.order_no.like(like), Order.plan_name.like(like))
        )
    return list(db.scalars(stmt))


# ---------- 全局统计 ----------

def get_global_stats(db: Session) -> dict:
    """
    后台全局统计。

    :return: 统计字典（结构见 AdminStatsOut）
    """
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    new_users_7d = db.scalar(
        select(func.count()).select_from(User).where(User.created_at >= week_ago)
    ) or 0
    total_contents = db.scalar(select(func.count()).select_from(CreationTask)) or 0
    success_contents = db.scalar(
        select(func.count()).select_from(CreationTask).where(CreationTask.status == 2)
    ) or 0
    total_chars = db.scalar(
        select(func.coalesce(func.sum(func.char_length(CreationTask.content)), 0))
        .where(CreationTask.status == 2)
    ) or 0
    active_users_7d = db.scalar(
        select(func.count(func.distinct(CreationTask.user_id)))
        .select_from(CreationTask)
        .where(CreationTask.created_at >= week_ago)
    ) or 0

    # ---------- 会员/订单统计（P2 会员系统新增） ----------
    total_orders = db.scalar(select(func.count()).select_from(Order)) or 0
    paid_orders = db.scalar(
        select(func.count()).select_from(Order).where(Order.status == 2)
    ) or 0
    paid_amount_fen = db.scalar(
        select(func.coalesce(func.sum(Order.amount), 0)).where(Order.status == 2)
    ) or 0

    return {
        "total_users": int(total_users),
        "new_users_7d": int(new_users_7d),
        "total_contents": int(total_contents),
        "success_contents": int(success_contents),
        "total_chars": int(total_chars),
        "active_users_7d": int(active_users_7d),
        # 会员/订单（元，金额分转元保留两位）
        "total_orders": int(total_orders),
        "paid_orders": int(paid_orders),
        "paid_amount_yuan": round(paid_amount_fen / 100, 2),
    }
