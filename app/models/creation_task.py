"""
创作任务数据模型（对应数据库 creation_tasks 表）

【这张表记录什么？】
每次"一键生成"就创建一条记录：用户是谁、什么主题、哪个平台、
生成过程中走到哪一步、最终结果是什么、质量分多少……

【用途】
1. 历史记录：用户可以在"历史记录"页查看/复用之前的生成结果
2. 进度追踪：生成过程中记录 current_step，即使中断也能知道进行到哪
3. 后续数据统计：P2 的数据看板（生成量、平台分布）都从这表统计

【与 users 表的关系】
每行任务都属于一个用户（user_id 外键关联 users 表）。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class CreationTask(Base):
    __tablename__ = "creation_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 所属用户（外键：指向 users 表的 id）
    # ondelete="CASCADE"：用户被删除时，其创作记录一并删除，避免孤儿数据
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # ---------- 生成参数 ----------
    keyword: Mapped[str] = mapped_column(String(200), default="")  # 用户输入的关键词/主题
    platform: Mapped[str] = mapped_column(String(20), default="")  # 目标平台
    selected_title: Mapped[str] = mapped_column(String(500), default="")  # 用户最终选择的选题标题

    # ---------- 状态与进度 ----------
    # 状态机：0=排队中 1=生成中 2=已完成 3=失败
    status: Mapped[int] = mapped_column(Integer, default=0, comment="0:排队中 1:生成中 2:已完成 3:失败")
    # 记录当前进行到的智能体步骤名（topic/logic/writer/polish/layout/quality）
    current_step: Mapped[str] = mapped_column(String(50), default="")

    # ---------- 生成结果 ----------
    # 正文（TEXT 类型，最长 65535 字符，足够存 2000+ 字文章）
    content: Mapped[str] = mapped_column(Text, default="")
    # 生成的质量分（0-100，MVP 阶段暂不深度使用，预留字段）
    quality_score: Mapped[int] = mapped_column(Integer, default=0)
    # 敏感词检查报告（JSON 字符串，如 {"has_sensitive": false, "words": []}）
    sensitive_report: Mapped[str] = mapped_column(Text, default="")
    # 失败原因（status=3 时记录错误信息，方便排查）
    error_message: Mapped[str] = mapped_column(String(500), default="")

    # ---------- 收藏标记（历史记录增强） ----------
    # 1=已收藏 0=未收藏（用户标记优质内容，方便快速找回）
    is_favorite: Mapped[int] = mapped_column(Integer, default=0, comment="1:已收藏 0:未收藏")

    # ---------- 时间戳 ----------
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关联用户对象（查询时 user.task 用法不常用，主要是给后台管理看关联数据用）
    user = relationship("User", backref="tasks")
