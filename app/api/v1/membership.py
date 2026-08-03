"""
会员中心接口：套餐列表 / 我的会员 / 下单 / 虚拟支付 / 订单列表

【购买流程（演示模式）】
1. 用户选套餐 → POST /orders 创建订单（返回订单号）
2. 用户点"模拟支付" → POST /orders/{order_no}/pay
3. 订单置为已支付 → 自动开通/续费会员

【真实支付怎么扩展？】
- 微信/支付宝渠道：需要商户资质，在 .env 开启 WECHAT_PAY_ENABLED/ALIPAY_PAY_ENABLED，
  然后在下单接口返回"支付参数"（二维码/H5 URL），并新增一个支付回调接口
  （支付平台 → 后端 notify）处理异步回调。开通会员的 activate_membership 已可复用。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import BizException
from app.db.session import get_db
from app.models.user import User
from app.schemas.membership import (
    MembershipOut,
    OrderCreate,
    OrderOut,
    PayResultOut,
    PlanOut,
)
from app.services import membership_service

router = APIRouter(prefix="/api/v1/membership", tags=["会员中心"])


@router.get("/plans", response_model=list[PlanOut], summary="套餐列表")
def plan_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PlanOut]:
    """
    返回可购买/展示的套餐（免费版 + 上架的付费套餐，按排序权重）。
    前端据此渲染套餐卡片（价格/权益/介绍）。
    """
    plans = membership_service.get_plan_list(db, include_off_shelf=False)
    return [PlanOut.from_dict(p) for p in plans]


@router.get("/me", response_model=MembershipOut, summary="我的会员状态")
def my_membership(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MembershipOut:
    """
    查询当前用户的会员状态：当前套餐、是否有效、到期时间、剩余天数。
    前端"会员中心"页顶部展示；免费用户返回内置免费版。
    """
    return MembershipOut(**membership_service.get_user_membership(db, current_user.id))


@router.post("/orders", response_model=OrderOut, summary="创建订单")
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderOut:
    """
    下单：选择套餐 + 支付渠道，创建一笔"待支付"订单。

    【演示模式注意】
    渠道 virtual 直接可支付；wechat/alipay 因未配置商户资质会被拒绝
    （提示走模拟支付），配置了资质后即可正常创建。
    """
    order = membership_service.create_order(db, current_user, data.plan_id, data.channel)
    return OrderOut.from_order(order)


@router.post("/orders/{order_no}/pay", response_model=PayResultOut, summary="模拟支付")
def pay_order(
    order_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PayResultOut:
    """
    模拟支付：把待支付订单标记为已支付，并自动开通/续费会员。

    【幂等保证】
    同一笔订单重复调用不会重复开通（第二次返回 already_paid=True）。
    """
    order = membership_service.get_order_by_no(db, current_user.id, order_no)
    if not order:
        raise BizException("订单不存在", status_code=404)
    result = membership_service.pay_order(db, order)
    return PayResultOut(**result)


@router.post("/orders/{order_no}/cancel", response_model=dict, summary="取消订单")
def cancel_order(
    order_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消一笔待支付订单（已支付/已取消的订单不能取消）。"""
    order = membership_service.get_order_by_no(db, current_user.id, order_no)
    if not order:
        raise BizException("订单不存在", status_code=404)
    membership_service.cancel_order(db, order)
    return {"message": "订单已取消"}


@router.get("/orders", response_model=list[OrderOut], summary="我的订单列表")
def order_list(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OrderOut]:
    """查询当前用户的全部订单（最新在前），含支付状态。"""
    orders = membership_service.get_user_orders(db, current_user.id, limit)
    return [OrderOut.from_order(o) for o in orders]
