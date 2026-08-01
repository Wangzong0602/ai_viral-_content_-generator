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
            from app.core.exceptions import BizException

            raise BizException(
                f"不支持的平台：{self.platform}，可选 {SUPPORTED_PLATFORMS}",
                status_code=422,
            )


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


class AdaptRequest(BaseModel):
    """
    多平台适配请求模型。

    - content：需要适配的原文（通常是已生成的爆文）
    - platforms：目标平台列表（至少 1 个，最多全部支持）
    - source_platform：原文所属平台（可选，用于提示词说明来源）
    """

    content: str = Field(..., min_length=50, max_length=20000, description="原文内容")
    platforms: list[str] = Field(..., min_length=1, max_length=10, description="目标平台列表")
    source_platform: str | None = Field(default=None, max_length=20, description="原文所属平台（可选）")

    def validate_platforms(self) -> None:
        """校验平台列表合法性（去重 + 必须在支持列表内）。

        注意：抛 BizException 而不是 ValueError——
        ValueError 不被全局异常处理器接管会变成 500，BizException 会转成 422。
        """
        # 去重（保持顺序）
        seen: list[str] = []
        for p in self.platforms:
            if p not in seen:
                seen.append(p)
        self.platforms = seen
        # 校验每个平台是否支持
        for p in self.platforms:
            if p not in SUPPORTED_PLATFORMS:
                from app.core.exceptions import BizException

                raise BizException(
                    f"不支持的平台：{p}，可选 {SUPPORTED_PLATFORMS}",
                    status_code=422,
                )


class AdaptItemOut(BaseModel):
    """单个平台适配结果。"""

    platform: str  # 平台名
    content: str  # 适配后的内容
    success: bool  # 是否成功
    error: str = ""  # 失败原因（success=False 时）


class AdaptResponse(BaseModel):
    """多平台适配响应。"""

    results: list[AdaptItemOut]


class AnalyzeRequest(BaseModel):
    """
    爆文逆向分析请求模型。

    支持两种输入：
    - 链接：input_text 填文章 URL，服务端自动抓取
    - 内容：input_text 直接填文章全文
    """

    input_text: str = Field(..., min_length=10, max_length=30000, description="文章链接或文章内容")


class AnalyzeReportOut(BaseModel):
    """分析报告中的单个要素（结构固定，内容为文本）。"""

    title_hook: str = ""
    opening_3s: str = ""
    content_structure: str = ""
    emotion_points: str = ""
    cta: str = ""
    seo_keywords: str = ""
    overall: str = ""


class AnalyzeResponse(BaseModel):
    """爆文逆向分析响应。"""

    title: str = ""  # 文章标题（链接抓取时有值）
    content_len: int  # 正文长度
    report: AnalyzeReportOut  # 拆解报告
