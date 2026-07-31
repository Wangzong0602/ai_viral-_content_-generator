"""
内容创作相关数据模型（请求/响应结构定义）

【三个模型的用途】
- CreateRequest：前端提交"一键生成"的请求参数
- TopicOut：选题智能体的单个选题（前端展示 + 用户选择）
- TopicsOut：选题列表响应（第一步：生成选题给用户选）
"""

from datetime import datetime

from pydantic import BaseModel, Field

# 支持的目标平台列表（新增平台时在这里加，同时需要对应的排版提示词）
SUPPORTED_PLATFORMS = ["小红书", "公众号", "知乎"]


class CreateRequest(BaseModel):
    """
    一键生成请求模型。
    step 表示"从哪一步开始"：
    - topics：只生成选题列表（前端展示给用户选）
    - full：用户已选好选题，直接跑完整创作流程
    """

    keyword: str = Field(..., min_length=1, max_length=200, description="主题/关键词")
    platform: str = Field(..., description="目标平台（小红书/公众号/知乎）")
    step: str = Field(default="topics", description="topics=生成选题 full=完整创作")
    selected_title: str | None = Field(default=None, max_length=500, description="用户选择的选题标题")

    def validate_platform(self) -> None:
        """校验平台是否支持（调用方在路由里手动调用）。"""
        if self.platform not in SUPPORTED_PLATFORMS:
            raise ValueError(f"不支持的平台：{self.platform}，可选 {SUPPORTED_PLATFORMS}")


class TopicOut(BaseModel):
    """单个选题的输出结构。"""

    title: str
    summary: str = ""
    target_audience: str = ""
    expected_effect: str = ""


class TopicsOut(BaseModel):
    """选题列表响应。"""

    keyword: str
    platform: str
    topics: list[TopicOut]


class TaskOut(BaseModel):
    """
    创作任务信息（历史记录用）。
    model_config = ConfigDict(from_attributes=True) 允许从 ORM 对象直接转换。
    """

    id: int
    keyword: str
    platform: str
    selected_title: str
    status: int
    content: str
    quality_score: int
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
