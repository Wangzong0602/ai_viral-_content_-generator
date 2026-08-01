"""
批量任务数据模型（对应数据库 batch_tasks 表）

【用途】
批量内容生成：一次提交多个关键词，后台队列逐篇生成。
- batch_tasks：一个批量任务（用户提交的一批关键词）
- batch_items：批量任务里的每一篇（一个关键词 → 一篇文章）

【与 creation_tasks 的关系】
每篇生成的正文仍然写入 creation_tasks（历史记录统一展示），
batch_items 记录"这篇属于哪个批量任务、状态如何"。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BatchTask(Base):
    """批量任务主表。"""

    __tablename__ = "batch_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(200), default="")  # 批量任务名称
    platform: Mapped[str] = mapped_column(String(20), default="")  # 目标平台

    # 状态：0=排队中 1=生成中 2=已完成 3=部分失败 4=失败
    status: Mapped[int] = mapped_column(Integer, default=0, comment="0:排队中 1:生成中 2:已完成 3:部分失败 4:失败")

    total: Mapped[int] = mapped_column(Integer, default=0)  # 总篇数
    success_count: Mapped[int] = mapped_column(Integer, default=0)  # 成功篇数
    fail_count: Mapped[int] = mapped_column(Integer, default=0)  # 失败篇数

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BatchItem(Base):
    """批量任务明细表（每个关键词一篇）。"""

    __tablename__ = "batch_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batch_tasks.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    keyword: Mapped[str] = mapped_column(String(200), default="")  # 本篇关键词
    # 状态：0=排队中 1=生成中 2=已完成 3=失败
    status: Mapped[int] = mapped_column(Integer, default=0, comment="0:排队中 1:生成中 2:已完成 3:失败")
    error_message: Mapped[str] = mapped_column(String(500), default="")  # 失败原因
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 关联的创作任务 ID（正文在 creation_tasks）

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
