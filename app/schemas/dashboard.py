"""
个人数据看板的数据模型（Pydantic v2 响应校验）
"""

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    """概览统计卡片。"""

    total_count: int = 0  # 总创作篇数
    total_chars: int = 0  # 总字数
    avg_quality: float = 0.0  # 平均质量分
    failed_count: int = 0  # 失败篇数
    saved_hours: float = 0.0  # 节省时间（小时）


class TrendPoint(BaseModel):
    """趋势图单点（某天创作数）。"""

    date: str
    count: int


class PlatformStat(BaseModel):
    """平台分布单条。"""

    platform: str
    count: int


class QualityStat(BaseModel):
    """质量分布单条。"""

    range: str  # 分数段标签（如 "90+"）
    count: int


class DashboardOverview(BaseModel):
    """数据看板总响应。"""

    summary: DashboardSummary
    trend: list[TrendPoint] = Field(default_factory=list)
    platforms: list[PlatformStat] = Field(default_factory=list)
    quality_dist: list[QualityStat] = Field(default_factory=list)
