"""
订单数据模型（对应数据库 orders 表）

【这个表存什么？】
用户购买会员的每一笔订单：买了哪个套餐、付了多少钱、用的什么渠道、
现在是什么状态（待支付/已支付/已取消/已退款）。

【订单状态机（status 字段）】
1 = 待支付：订单已创建，还没付钱
2 = 已支付：钱已到账，会员已开通（或续费）
3 = 已取消：用户主动取消 / 超时未支付
4 = 已退款：管理员退款（本期演示模式不实现，字段先预留）

【为什么把 plan_name 冗余一份存进来？】
订单创建后套餐可能被管理员改名或下架。订单是"历史事实"，
必须记录购买当时的价格和名称，不能跟着套餐表变动——
这就是数据库设计里的"冗余快照"思想。
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Order(Base):
    """会员订单表（orders）。"""

    __tablename__ = "orders"

    # 主键：自增
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 订单号（业务上唯一，给用户看的编号）。
    # 不用主键 id 的原因：订单号通常要带时间/随机字符（如 202608031200001234），
    # 且订单号是给外部（支付渠道/用户）对账用的，不能预测、不能重复
    order_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    # 下单用户 ID（关联 users 表）
    user_id: Mapped[int] = mapped_column(Integer, index=True)

    # 购买的套餐 ID + 名称快照（见文件顶部注释：为什么冗余名称）
    plan_id: Mapped[int] = mapped_column(Integer)
    plan_name: Mapped[str] = mapped_column(String(50), default="")

    # 成交金额（分）。从套餐价格复制过来存快照，套餐改价不影响历史订单
    amount: Mapped[int] = mapped_column(Integer, default=0, comment="成交金额（分）")

    # 支付渠道：
    #   virtual = 演示支付（本项目 MVP 用，点一下直接成功）
    #   wechat  = 微信支付（骨架预留，需商户资质后启用）
    #   alipay  = 支付宝支付（骨架预留，需商户资质后启用）
    channel: Mapped[str] = mapped_column(String(20), default="virtual")

    # 状态：1=待支付 2=已支付 3=已取消 4=已退款
    status: Mapped[int] = mapped_column(Integer, default=1, comment="1:待支付 2:已支付 3:已取消 4:已退款")

    # 支付成功时间（未支付则为 NULL，可空）
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 创建时间
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
