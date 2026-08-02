"""
内容模板接口

【接口说明】
GET /api/v1/content/templates?platform=小红书
- 返回模板列表（可选按平台过滤）
- 需要登录
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.template import TemplateOut
from app.services import template_service

router = APIRouter(prefix="/api/v1/content/templates", tags=["内容模板"])


@router.get("", response_model=list[TemplateOut], summary="内容模板列表")
def template_list(
    platform: str | None = Query(default=None, description="按平台过滤（可选）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TemplateOut]:
    """查询可用内容模板（可按平台过滤，前端按当前平台联动展示）。"""
    templates = template_service.get_templates(db, platform)
    return [TemplateOut.from_model(t) for t in templates]
