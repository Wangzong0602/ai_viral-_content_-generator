"""
批量内容生成接口

【接口说明】
- POST /api/v1/content/batch：创建批量任务（输入关键词列表 → 后台逐篇生成）
- GET  /api/v1/content/batch：批量任务列表
- GET  /api/v1/content/batch/{id}：批量任务详情（含每篇状态）

【异步说明】
创建接口只做"入库 + 投递 Celery 队列"，立即返回（后台 worker 逐篇生成），
所以用户提交后可以轮询详情接口看进度（前端定时刷新）。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.batch import (
    BatchCreateRequest,
    BatchDetailOut,
    BatchItemOut,
    BatchOut,
)
from app.schemas.content import SUPPORTED_PLATFORMS
from app.services import batch_service
from app.core.exceptions import BizException

router = APIRouter(prefix="/api/v1/content/batch", tags=["批量生成"])


@router.post("", response_model=BatchOut, summary="创建批量任务")
def create_batch(
    data: BatchCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchOut:
    """创建批量任务：解析关键词列表 → 入库 → 投递 Celery 后台生成。"""
    # 平台校验
    if data.platform not in SUPPORTED_PLATFORMS:
        raise BizException(
            f"不支持的平台：{data.platform}，可选 {SUPPORTED_PLATFORMS}", status_code=422
        )
    # 解析关键词
    keywords = batch_service.parse_keywords(data.keywords_text)
    # 创建并投递
    batch = batch_service.create_batch(
        db, current_user.id, data.name or "", data.platform, keywords
    )
    return BatchOut.model_validate(batch)


@router.get("", response_model=list[BatchOut], summary="批量任务列表")
def batch_list(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BatchOut]:
    """查询当前用户的批量任务列表（最新在前）。"""
    batches = batch_service.get_batch_list(db, current_user.id, limit)
    return [BatchOut.model_validate(b) for b in batches]


@router.get("/{batch_id}", response_model=BatchDetailOut, summary="批量任务详情")
def batch_detail(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchDetailOut:
    """查询批量任务详情（含每篇状态，前端轮询进度用）。"""
    batch = batch_service.get_batch(db, current_user.id, batch_id)
    items = batch_service.get_batch_items(db, batch_id)
    detail = BatchDetailOut.model_validate(batch)
    detail.items = [
        BatchItemOut(
            id=it.id,
            keyword=it.keyword,
            status=it.status,
            error_message=it.error_message,
            task_id=it.task_id,
        )
        for it in items
    ]
    return detail
