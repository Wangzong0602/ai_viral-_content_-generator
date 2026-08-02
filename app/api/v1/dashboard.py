"""
个人数据看板接口

【接口说明】
GET /api/v1/dashboard/overview?days=30
- 返回用户的创作统计：概览卡片 + 近 N 天趋势 + 平台分布 + 质量分布
- 需要登录（Bearer Token）
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import (
    DashboardOverview,
    DashboardSummary,
    PlatformStat,
    QualityStat,
    TrendPoint,
)
from app.services import dashboard_service

router = APIRouter(prefix="/api/v1/dashboard", tags=["数据看板"])


@router.get("/overview", response_model=DashboardOverview, summary="数据看板总览")
def overview(
    days: int = Query(default=30, ge=7, le=90, description="趋势统计天数（近 N 天）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardOverview:
    """获取用户创作数据统计（只统计当前登录用户自己的数据）。"""
    data = dashboard_service.get_overview(db, current_user.id, days)
    return DashboardOverview(
        summary=DashboardSummary(**data["summary"]),
        trend=[TrendPoint(**t) for t in data["trend"]],
        platforms=[PlatformStat(**p) for p in data["platforms"]],
        quality_dist=[QualityStat(**q) for q in data["quality_dist"]],
    )
