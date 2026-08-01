"""
配图记录数据模型（对应数据库 image_records 表）

【为什么需要这张表？】
之前配图只返回 URL 给前端展示，没有落库——
导致历史记录里只有文字、没有图片（用户反馈的缺陷）。
这张表把每次生成的配图记录下来，关联到创作任务：
- 历史记录详情页可以看到该文章生成的配图
- 后续数据看板可统计配图数量/风格分布（P2）

【去重策略】
同一篇任务（task_id）同一场景（scene）重复生成（换一张）时，
【更新】原记录而不是新增——保证每篇任务每个场景只保留最新一张。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ImageRecord(Base):
    __tablename__ = "image_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 所属用户（外键）
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # 关联的创作任务（外键；允许为空——用户也可能在未关联任务时配图）
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("creation_tasks.id", ondelete="CASCADE"), index=True, nullable=True
    )

    # 图片信息
    url: Mapped[str] = mapped_column(String(255))  # 本地访问 URL（/images/...）
    scene: Mapped[str] = mapped_column(String(500), default="")  # 场景描述
    style: Mapped[str] = mapped_column(String(50), default="")  # 配图风格
    operation: Mapped[str] = mapped_column(String(20), default="generate")  # generate/regenerate

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
