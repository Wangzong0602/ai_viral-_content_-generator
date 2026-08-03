"""
会员记录数据模型（对应数据库 memberships 表）

【这个表存什么？】
用户"当前会员身份"的历史记录。每次开通/续费会员都会产生一条记录：
- 免费用户：没有记录（免费版是内置常量，不入库）
- 开通专业版：一条记录，start_date=今天，end_date=今天+30天
- 到期后续费：同一套餐 → 在"最后一条有效记录"上延长 end_date；
  换套餐 → 旧记录置为取消（status=3），新开一条

【为什么单独建表而不是在 users 表加两个字段（plan、expire）？】
- 需求文档明确要求记录会员历史（以后做"会员续费率"统计要用）
- 一张表一个用户一行：升级/降级/续费的历史全部丢失，没法追溯
所以会员是"流水记录"：users 表只存账号信息，membership 流水单独一张表。

【为什么 plan_name 也要冗余？】
和 orders 表同理：套餐被改名/下架后，会员记录要能显示"当年买的套餐叫啥"。
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Membership(Base):
    """会员记录表（memberships）。"""

    __tablename__ = "memberships"

    # 主键：自增
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 用户 ID（关联 users 表，加索引：查"这个用户有没有会员"会按它查）
    user_id: Mapped[int] = mapped_column(Integer, index=True)

    # 套餐 ID + 名称快照（理由见文件顶部注释）
    plan_id: Mapped[int] = mapped_column(Integer)
    plan_name: Mapped[str] = mapped_column(String(50), default="")

    # 会员有效期：生效开始时间 ~ 到期时间
    # （end_date < 当前时间 = 已过期，查询时统一判断，不需要定时任务扫描）
    start_date: Mapped[datetime] = mapped_column(DateTime)
    end_date: Mapped[datetime] = mapped_column(DateTime, index=True)

    # 状态：1=有效 2=已过期 3=已取消（换套餐/降级时旧记录标 3）
    status: Mapped[int] = mapped_column(Integer, default=1, comment="1:有效 2:过期 3:取消")

    # 创建时间
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
