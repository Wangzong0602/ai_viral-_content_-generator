"""
会员套餐数据模型（对应数据库 plans 表）

【这个表存什么？】
会员套餐的定义：专业版 199 元/月、企业版 999 元/月……
每个套餐是一行，管理员可以在后台增删改（上架/下架）。

【价格为什么用整数存"分"而不是小数存"元"？】
金额计算用浮点小数（如 0.1 + 0.2 = 0.30000000000000004）会有精度误差，
行业内统一用"分"（整数）存钱：199 元存 19900 分，计算精确无误差，
展示给用户时再除以 100 转成元。

【features 为什么用 JSON？】
每个套餐的权益（每天生成次数、批量上限……）结构不同，且未来可能加新权益。
如果每个权益建一列，以后加权益就要改表结构；
用 JSON 列，权益自由增减，改动只发生在代码里，不用改数据库。
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Plan(Base):
    """会员套餐表（plans）。"""

    __tablename__ = "plans"

    # 主键：自增
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 套餐标识码（唯一，代码里用来判断是哪个套餐，如 pro/enterprise）
    # 注意：免费版不是套餐记录，是代码内置常量（见 membership_service.FREE_PLAN）
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)

    # 套餐名称（展示用，如"专业版"）
    name: Mapped[str] = mapped_column(String(50))

    # 价格（单位：分）。199 元 = 19900
    price: Mapped[int] = mapped_column(Integer, default=0, comment="价格（分）")

    # 有效期（天数）。30 = 开通后 30 天到期；0 表示永久
    duration_days: Mapped[int] = mapped_column(Integer, default=30)

    # 权益配置（JSON 对象）：daily_articles 每日生成次数、batch_limit 批量上限……
    # 具体字段含义见 membership_service.py 里的 FREE_PLAN / PRO_FEATURES / ENTERPRISE_FEATURES
    features: Mapped[dict] = mapped_column(JSON, default=dict)

    # 一句话介绍（展示在套餐卡片上，如"适合全职自媒体人"）
    description: Mapped[str] = mapped_column(String(500), default="")

    # 排序权重（数字越小越靠前，套餐卡片展示顺序）
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # 状态：1=上架（用户可见可买） 2=下架（隐藏，历史订单不受影响）
    status: Mapped[int] = mapped_column(Integer, default=1, comment="1:上架 2:下架")

    # 创建时间（数据库自动填）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
