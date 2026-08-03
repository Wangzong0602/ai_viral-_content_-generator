"""
会员/订单的数据模型（Pydantic v2 请求/响应校验）

【和 models/membership.py 的关系】
models/ 里是数据库 ORM 模型（怎么存）；
schemas/ 里是接口传输模型（怎么传）。
接口返回给前端的结构由这里定义，保证不泄露内部字段。
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.order import Order
from app.models.plan import Plan


class PlanOut(BaseModel):
    """套餐响应（C 端展示 + 管理端通用）。"""

    id: int | None = None  # 免费版没有 id（不在数据库），允许为空
    code: str
    name: str
    # 价格用"元"展示（数据库存分，这里转换）
    price_yuan: float = 0
    duration_days: int
    features: dict = Field(default_factory=dict)  # 权益明细（前端渲染权益清单用）
    description: str = ""
    sort_order: int = 0
    status: int = 1

    @classmethod
    def from_dict(cls, data: dict) -> "PlanOut":
        """把 service 层的套餐字典转成响应模型（统一把分转成元）。"""
        return cls(
            id=data.get("id"),
            code=data.get("code", ""),
            name=data.get("name", ""),
            price_yuan=round((data.get("price") or 0) / 100, 2),
            duration_days=data.get("duration_days", 0),
            features=data.get("features") or {},
            description=data.get("description", ""),
            sort_order=data.get("sort_order", 0),
            status=data.get("status", 1),
        )


class MembershipOut(BaseModel):
    """我的会员状态响应。"""

    plan: PlanOut
    is_active: bool  # 是否在有效期内
    start_date: datetime | None = None
    end_date: datetime | None = None
    days_left: int = 0  # 剩余天数
    last_end_date: datetime | None = None  # 最近会员到期时间（已过期提示用）


class OrderCreate(BaseModel):
    """下单请求：选哪个套餐 + 用什么渠道支付。"""

    plan_id: int = Field(..., ge=1, description="套餐 ID")
    channel: str = Field(default="virtual", description="支付渠道：virtual/wechat/alipay")


class OrderOut(BaseModel):
    """订单响应（用户自己的订单列表）。"""

    id: int
    order_no: str
    plan_name: str
    amount_yuan: float  # 金额（元）
    channel: str
    status: int  # 1待支付 2已支付 3已取消 4已退款
    paid_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_order(cls, order: Order) -> "OrderOut":
        """ORM 转响应模型（金额分→元）。"""
        return cls(
            id=order.id,
            order_no=order.order_no,
            plan_name=order.plan_name,
            amount_yuan=round(order.amount / 100, 2),
            channel=order.channel,
            status=order.status,
            paid_at=order.paid_at,
            created_at=order.created_at,
        )


class PayResultOut(BaseModel):
    """支付结果响应。"""

    message: str
    already_paid: bool = False  # 是否重复支付（幂等提示）
    membership_id: int | None = None


class QuotaItemOut(BaseModel):
    """单个动作的今日用量。"""

    used: int = 0  # 今日已用（-1 时无意义）
    limit: int = 0  # 上限（-1=不限，0=未开放）
    remaining: int = 0  # 剩余（-1=不限）


class QuotaUsageOut(BaseModel):
    """今日权益用量响应（会员中心展示）。"""

    article: QuotaItemOut  # 文章生成（每日次数）
    analyze: QuotaItemOut  # 爆文分析（每日次数）
    image: QuotaItemOut  # AI 配图（每日张数）
    batch: QuotaItemOut  # 批量生成（limit=单次篇数上限）


# ---------- 管理端 ----------

class AdminPlanCreate(BaseModel):
    """管理端新增套餐请求。"""

    code: str = Field(..., min_length=2, max_length=30, description="套餐标识（唯一）")
    name: str = Field(..., min_length=1, max_length=50, description="套餐名称")
    price_yuan: float = Field(..., ge=0, description="价格（元）")
    duration_days: int = Field(default=30, ge=1, description="有效期天数")
    features: dict = Field(default_factory=dict, description="权益配置 JSON")
    description: str = Field(default="", max_length=500)
    sort_order: int = 0
    status: int = Field(default=1, ge=1, le=2, description="1:上架 2:下架")


class AdminPlanUpdate(BaseModel):
    """管理端编辑套餐请求（字段全可选，只更新传了的）。"""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    price_yuan: float | None = Field(default=None, ge=0)
    duration_days: int | None = Field(default=None, ge=1)
    features: dict | None = None
    description: str | None = Field(default=None, max_length=500)
    sort_order: int | None = None
    status: int | None = Field(default=None, ge=1, le=2)


class AdminOrderOut(BaseModel):
    """管理端订单列表项（比用户订单多用户昵称）。"""

    id: int
    order_no: str
    user_id: int
    user_nickname: str = ""
    plan_name: str
    amount_yuan: float
    channel: str
    status: int
    paid_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_order(cls, order: Order, user_nickname: str = "") -> "AdminOrderOut":
        out = cls(
            id=order.id,
            order_no=order.order_no,
            user_id=order.user_id,
            user_nickname=user_nickname,
            plan_name=order.plan_name,
            amount_yuan=round(order.amount / 100, 2),
            channel=order.channel,
            status=order.status,
            paid_at=order.paid_at,
            created_at=order.created_at,
        )
        return out


class AdminMembershipGrant(BaseModel):
    """
    管理端手动开通/续期会员请求。

    :param plan_id: 目标套餐 ID（免费版无 ID，不能选）
    :param days: 赠送天数，不传则用套餐自带的 duration_days
    :param note: 操作备注（写进返回消息，供审计）
    """

    plan_id: int = Field(..., ge=1, description="套餐 ID")
    days: int | None = Field(default=None, ge=1, le=3650, description="赠送天数（默认套餐有效期）")
    note: str = Field(default="管理员手动开通", max_length=100)
