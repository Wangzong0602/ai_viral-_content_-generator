"""
批量内容生成的数据模型（Pydantic v2 请求/响应校验）
"""

from datetime import datetime

from pydantic import BaseModel, Field


class BatchCreateRequest(BaseModel):
    """创建批量任务请求模型。"""

    name: str | None = Field(default=None, max_length=200, description="任务名称（可选）")
    platform: str = Field(..., description="目标平台（小红书/公众号/知乎）")
    # 关键词输入：支持每行一个，或逗号/分号/顿号分隔
    keywords_text: str = Field(..., min_length=1, max_length=10000, description="关键词列表（每行一个或分隔符隔开）")


class BatchItemOut(BaseModel):
    """批量任务单篇状态。"""

    id: int
    keyword: str
    status: int  # 0=排队中 1=生成中 2=已完成 3=失败
    error_message: str = ""
    task_id: int | None = None  # 关联的创作任务（正文在 creation_tasks）


class BatchOut(BaseModel):
    """批量任务信息。"""

    id: int
    name: str
    platform: str
    status: int  # 0=排队中 1=生成中 2=已完成 3=部分失败
    total: int
    success_count: int
    fail_count: int
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class BatchDetailOut(BatchOut):
    """批量任务详情（含每篇状态）。"""

    items: list[BatchItemOut] = Field(default_factory=list)
