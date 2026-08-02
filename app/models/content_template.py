"""
内容模板数据模型（对应数据库 content_templates 表）

【用途】
各平台爆文结构模板：用户创作时可选一个模板，
把模板的"结构要求"注入选题/逻辑分析智能体的提示词，
让生成的文章严格按爆款结构产出（痛点共鸣型/清单盘点型/故事型等）。

【结构字段】
structure 存 JSON 字符串，包含：
{
  "hook": "标题钩子策略",
  "opening": "开头策略",
  "body": "正文结构",
  "cta": "结尾行动召唤"
}

【与平台的关系】
每个模板属于一个平台（小红书/公众号/知乎），
新增平台时同步添加对应模板（种子数据见 app/services/template_service.py）。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ContentTemplate(Base):
    __tablename__ = "content_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))  # 模板名称（如"痛点共鸣型"）
    platform: Mapped[str] = mapped_column(String(20), index=True)  # 适用平台
    description: Mapped[str] = mapped_column(String(300), default="")  # 模板说明
    # 结构要求（JSON 字符串：hook/opening/body/cta）
    structure: Mapped[str] = mapped_column(Text, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否启用
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
