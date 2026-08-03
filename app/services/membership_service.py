"""
会员服务：套餐查询 / 下单 / 虚拟支付 / 会员开通续费

【为什么免费版不进数据库？】
免费版是"每个注册用户天然拥有的身份"，不需要管理员管理、不能购买，
所以写死在代码里（FREE_PLAN 常量），查询套餐列表时和数据库套餐合并返回。
专业版/企业版才是数据库里的套餐记录（管理员可增删改）。

【金额单位】
数据库和计算都用"分"（整数），避免浮点误差；API 返回给前端时转成"元"。
"""

import random
import string
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BizException
from app.models.membership import Membership
from app.models.order import Order
from app.models.plan import Plan
from app.models.user import User

# ---------- 免费版定义（内置常量，不入库） ----------

FREE_PLAN = {
    "code": "free",
    "name": "免费版",
    "price": 0,  # 分（0 元）
    "duration_days": 0,
    "features": {
        "daily_articles": 3,  # 每天文章生成次数
        "image_per_article": 0,  # 每篇配图数量（0 = 不提供 AI 配图）
        "batch_limit": 0,  # 批量生成单次上限（0 = 不可用）
        "analyze_daily": 3,  # 每天爆文逆向分析次数
        "export_formats": ["txt", "md"],  # 可用导出格式
        "priority": "普通队列",  # 生成队列优先级
    },
    "description": "注册即享：每天 3 次 AI 创作，适合新手体验",
    "sort_order": 0,
    "status": 1,
}

# 套餐权益明细（建种子套餐时用，管理员可在后台改）
PRO_FEATURES = {
    "daily_articles": 100,
    "image_per_article": 10,
    "batch_limit": 50,
    "analyze_daily": 50,
    "export_formats": ["txt", "md", "html"],
    "priority": "优先队列",
}

ENTERPRISE_FEATURES = {
    "daily_articles": -1,  # -1 表示不限次
    "image_per_article": -1,
    "batch_limit": 200,
    "analyze_daily": -1,
    "export_formats": ["txt", "md", "html", "docx"],
    "priority": "最高优先级",
}


def init_seed_plans(db: Session) -> None:
    """
    初始化种子套餐（幂等：按 code 判断，已存在就跳过）。

    首次启动时写入专业版/企业版两个套餐，之后管理员可在后台修改。
    """
    seeds = [
        {
            "code": "pro",
            "name": "专业版",
            "price": 19900,  # 199 元
            "duration_days": 30,
            "features": PRO_FEATURES,
            "description": "每天 100 次 AI 创作 + 每篇 10 张配图，适合全职创作者",
            "sort_order": 1,
        },
        {
            "code": "enterprise",
            "name": "企业版",
            "price": 99900,  # 999 元
            "duration_days": 30,
            "features": ENTERPRISE_FEATURES,
            "description": "不限次数创作 + 批量生成 200 篇，适合工作室/MCN",
            "sort_order": 2,
        },
    ]
    for seed in seeds:
        exists = db.scalar(select(Plan).where(Plan.code == seed["code"]))
        if exists:
            continue
        db.add(Plan(**seed))
    db.commit()


def get_plan_list(db: Session, include_off_shelf: bool = False) -> list[dict]:
    """
    查询套餐列表（免费版 + 上架的数据库套餐，按 sort_order 排序）。

    :param db: 数据库会话
    :param include_off_shelf: True=管理端用，下架的套餐也返回（status 标记为 2）
    """
    stmt = select(Plan).order_by(Plan.sort_order.asc(), Plan.id.asc())
    if not include_off_shelf:
        stmt = stmt.where(Plan.status == 1)
    plans = [FREE_PLAN] + [p.to_dict() if hasattr(p, "to_dict") else _plan_to_dict(p) for p in db.scalars(stmt)]
    if include_off_shelf:
        return plans
    # C 端只返回上架的数据库套餐（免费版恒为 1）
    return [p for p in plans if p["status"] == 1]


def _plan_to_dict(plan: Plan) -> dict:
    """把 Plan ORM 对象转成字典（和 FREE_PLAN 同结构，方便前端统一处理）。"""
    return {
        "id": plan.id,
        "code": plan.code,
        "name": plan.name,
        "price": plan.price,
        "duration_days": plan.duration_days,
        "features": plan.features or {},
        "description": plan.description,
        "sort_order": plan.sort_order,
        "status": plan.status,
    }


def get_plan_by_id(db: Session, plan_id: int) -> Plan | None:
    """按 ID 查套餐（管理端用）。"""
    return db.get(Plan, plan_id)


def get_plan_by_code(db: Session, code: str) -> Plan | None:
    """按 code 查套餐（购买时校验套餐是否存在且上架）。"""
    return db.scalar(select(Plan).where(Plan.code == code))


# ---------- 订单 ----------

def generate_order_no() -> str:
    """
    生成订单号：时间戳 + 随机字符。
    如 20260803123456 + 4 位随机 = 20 位，长度在 32 以内。
    随机字符防止订单号被预测（安全：不能让别人猜出订单号乱操作）。
    """
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{ts}{rand}"


def create_order(db: Session, user: User, plan_id: int, channel: str) -> Order:
    """
    创建订单（待支付状态）。

    【校验链路】
    1. 套餐必须存在且上架（下架套餐不能下单）
    2. 支付渠道必须合法（virtual/wechat/alipay）
    3. wechat/alipay 是骨架渠道：未在 .env 启用配置时直接拒绝
       （真实接入后：下单接口要调用支付 SDK 生成支付参数）

    【为什么渠道校验放服务层而不是 API 层？】
    下单逻辑（校验+快照）以后接入真实支付也要复用，放服务层最合适。
    """
    if plan_id == FREE_PLAN.get("id"):
        raise BizException("免费版无需购买")
    plan = db.get(Plan, plan_id)
    if not plan:
        raise BizException("套餐不存在")
    if plan.status != 1:
        raise BizException("该套餐已下架")

    _check_channel(channel)

    order = Order(
        order_no=generate_order_no(),
        user_id=user.id,
        plan_id=plan.id,
        plan_name=plan.name,
        amount=plan.price,
        channel=channel,
        status=1,  # 待支付
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def _check_channel(channel: str) -> None:
    """
    校验支付渠道可用性。

    当前是"虚拟支付 + 渠道骨架"模式：
    - virtual：演示支付，始终可用
    - wechat / alipay：真实支付渠道骨架。需要商户资质并在 .env 开启
      WECHAT_PAY_ENABLED / ALIPAY_PAY_ENABLED 才能用（本期默认关闭）。
    """
    if channel not in ("virtual", "wechat", "alipay"):
        raise BizException("不支持的支付渠道")
    if channel == "wechat" and not settings.WECHAT_PAY_ENABLED:
        raise BizException("微信支付尚未开通（演示模式请选择\"模拟支付\"）")
    if channel == "alipay" and not settings.ALIPAY_PAY_ENABLED:
        raise BizException("支付宝支付尚未开通（演示模式请选择\"模拟支付\"）")


def get_order_by_no(db: Session, user_id: int, order_no: str) -> Order | None:
    """按订单号查订单（必须校验归属用户，别人不能操作你的订单）。"""
    return db.scalar(
        select(Order).where(Order.order_no == order_no, Order.user_id == user_id)
    )


def pay_order(db: Session, order: Order) -> dict:
    """
    模拟支付：把"待支付"订单标记为已支付，并开通/续费会员。

    【真实支付接入后怎么改？】
    虚拟支付是"点了就说成功"。真实微信/支付宝支付流程是：
    1. 前端调用下单接口 → 返回支付参数（二维码/H5 URL）
    2. 用户扫码/跳转支付
    3. 支付平台回调后端 notify 接口（异步）
    4. 回调里验签 → 把订单置为已支付 → 开通会员
    所以真实模式下，"开通会员"会挪到回调处理函数里，
    但"开通/续费"的会员逻辑（activate_membership）完全可以复用本服务。

    【支付幂等性】
    同一笔订单重复点支付（前端抖动/用户刷新重试）不能重复开通两次会员：
    进来先判断 status != 1（待支付）直接返回"已支付"，不做任何事。
    """
    if order.status == 2:
        return {"message": "该订单已支付", "already_paid": True}
    if order.status != 1:
        raise BizException("订单状态不允许支付（已取消或已退款）")

    now = datetime.now()
    order.status = 2  # 已支付
    order.paid_at = now
    db.add(order)

    membership = activate_membership(db, order.user_id, order.plan_id, order.plan_name, now)
    db.commit()
    return {"message": "支付成功，会员已开通", "already_paid": False, "membership_id": membership.id}


def cancel_order(db: Session, order: Order) -> None:
    """取消订单（只有待支付订单能取消）。"""
    if order.status != 1:
        raise BizException("只有待支付订单可以取消")
    order.status = 3
    db.add(order)
    db.commit()


def activate_membership(
    db: Session,
    user_id: int,
    plan_id: int,
    plan_name: str,
    now: datetime,
    days: int | None = None,
) -> Membership:
    """
    开通/续费会员（核心逻辑，真实支付接入后也复用这里）。

    【续费 vs 新开】
    - 用户当前有"同一套餐"的有效会员 → 续费：end_date 往后顺延 duration_days
      （如 7月1日开通到7月31日，8月1日续费 → 到期日变 8月30日，不会丢 7 月的天数）
    - 其他情况（没会员 / 会员已过期 / 换套餐）→ 旧有效记录置为取消(3)，
      新建一条记录 start=now, end=now+duration

    :param days: 覆盖套餐默认时长（管理员手动赠予时传，支付流程不传）
    """
    duration = days or (db.get(Plan, plan_id).duration_days if db.get(Plan, plan_id) else 30)

    # 查用户当前"有效且未过期"的会员记录（status=1 且 end_date 在未来）
    current = db.scalar(
        select(Membership)
        .where(
            Membership.user_id == user_id,
            Membership.status == 1,
            Membership.end_date > now,
        )
        .order_by(Membership.end_date.desc())
    )

    if current and current.plan_id == plan_id:
        # 同一套餐续费：在现有到期日上顺延（而不是从今天重新算）
        current.end_date = current.end_date + timedelta(days=duration)
        db.add(current)
        return current

    # 换套餐 / 无有效会员：旧的取消，新开一条
    if current:
        current.status = 3
        db.add(current)
    membership = Membership(
        user_id=user_id,
        plan_id=plan_id,
        plan_name=plan_name,
        start_date=now,
        end_date=now + timedelta(days=duration),
        status=1,
    )
    db.add(membership)
    return membership


# ---------- 查询 ----------

def get_user_membership(db: Session, user_id: int) -> dict:
    """
    查询用户当前会员状态（C 端"我的会员"接口用）。

    :return: {
        plan: 套餐信息（免费版内置 / 数据库套餐）,
        is_active: 是否有效期内,
        start_date / end_date: 有效期,
        days_left: 剩余天数,
        last_end_date: 最近一条会员记录的到期时间（已过期时供前端提示用）,
    }
    """
    now = datetime.now()
    # 当前有效会员（status=1 且未过期）
    current = db.scalar(
        select(Membership)
        .where(
            Membership.user_id == user_id,
            Membership.status == 1,
            Membership.end_date > now,
        )
        .order_by(Membership.end_date.desc())
    )
    # 最近一条会员记录（不限状态，用于"已过期"提示）
    last = db.scalar(
        select(Membership)
        .where(Membership.user_id == user_id)
        .order_by(Membership.end_date.desc())
        .limit(1)
    )

    if not current:
        # 免费用户 / 会员已过期：返回内置免费版定义
        # last_end_date 非空 = 曾经有会员但已过期 → 前端显示"已过期，续费可恢复"
        return {
            "plan": FREE_PLAN,
            "is_active": False,  # 免费版没有"有效期"概念，标记 False 让前端显示"免费版"
            "start_date": None,
            "end_date": None,
            "days_left": 0,
            "last_end_date": last.end_date if last else None,
        }

    plan = db.get(Plan, current.plan_id)
    plan_dict = _plan_to_dict(plan) if plan else {"code": "unknown", "name": current.plan_name, "features": {}, "price": 0, "duration_days": 0, "description": "", "sort_order": 99, "status": 1}
    return {
        "plan": plan_dict,
        "is_active": True,
        "start_date": current.start_date,
        "end_date": current.end_date,
        "days_left": max((current.end_date - now).days, 0),
        "last_end_date": last.end_date if last else None,
    }


def get_user_orders(db: Session, user_id: int, limit: int = 50) -> list[Order]:
    """查询用户自己的订单列表（最新在前）。"""
    stmt = (
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))

