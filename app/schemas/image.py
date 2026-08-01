"""
AI 配图接口的数据模型（Pydantic v2 请求/响应校验）
"""

from typing import Literal

from pydantic import BaseModel, Field

# 支持的操作类型：
# - analyze：只做语义分析（返回场景列表，暂未使用，预留）
# - generate：生成图片（默认）
# - regenerate：重新生成某张图（前端"不满意换一张"）
OperationType = Literal["generate", "regenerate", "analyze"]

# 支持的配图风格（与 image_service.STYLES 的 key 一致）
StyleType = Literal["插画卡通", "写实摄影", "科技未来", "简约扁平", "国潮古风"]


class ImageGenerateRequest(BaseModel):
    """配图请求模型。"""

    content: str = Field(..., min_length=10, max_length=10000, description="文章内容（用于语义分析）")
    count: int = Field(default=3, ge=1, le=5, description="生成图片数量 1-5")
    style: StyleType = Field(default="插画卡通", description="配图风格")
    operation: OperationType = Field(default="generate", description="操作类型")
    # 重新生成时：需要原场景描述（保证重生成的是同一场景，风格一致）
    scene: str | None = Field(default=None, max_length=500, description="重生成时的场景描述")
    # 关联的创作任务 ID（用于历史记录展示配图，可空）
    task_id: int | None = Field(default=None, description="关联的创作任务 ID")


class ImageOut(BaseModel):
    """单张图片响应。"""

    url: str  # 图片本地访问 URL
    scene: str  # 场景描述


class ImageGenerateResponse(BaseModel):
    """配图响应模型。"""

    images: list[ImageOut]
