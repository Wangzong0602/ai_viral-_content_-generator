"""
批量内容生成服务：创建批量任务、解析关键词列表、进度查询

【批量任务生命周期】
创建（status=0 排队中）→ 每篇投递 Celery 任务 → worker 逐篇生成
→ 全部完成后 status=2（全成功）/ 3（部分失败）

【Celery 任务投递】
使用 celery group（分组）：一次投递 N 个任务，每个任务生成一篇。
group 支持并发执行（threads pool 多线程）。

【进度查询】
从 batch_tasks / batch_items 表读取：总篇数、成功数、失败数、每篇状态。
（进度存在数据库而不是 Celery backend，因为我们要在 FastAPI 里查询）
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BizException
from app.core.logger import logger
from app.models.batch_task import BatchItem, BatchTask
from app.tasks.batch_tasks import generate_one

# 单次批量最大篇数（防止滥用烧钱）
MAX_BATCH_ITEMS = 30


def parse_keywords(raw: str) -> list[str]:
    """
    解析用户输入的批量关键词列表。

    支持格式：
    - 每行一个关键词（推荐）
    - 逗号/分号/顿号分隔

    :param raw: 原始输入文本
    :return: 去重后的关键词列表（最多 MAX_BATCH_ITEMS 个）
    """
    # 按常见分隔符切分：换行/逗号/分号/顿号
    import re

    parts = re.split(r"[\n,，;；、]+", raw)
    keywords: list[str] = []
    for p in parts:
        k = p.strip()
        if k and k not in keywords:
            keywords.append(k)
    return keywords[:MAX_BATCH_ITEMS]


def create_batch(
    db: Session,
    user_id: int,
    name: str,
    platform: str,
    keywords: list[str],
) -> BatchTask:
    """
    创建批量任务并投递 Celery 任务。

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param name: 批量任务名称
    :param platform: 目标平台
    :param keywords: 关键词列表（已去重、已限长）
    :return: 创建的批量任务（含明细）
    """
    if not keywords:
        raise BizException("没有可用的关键词，请检查输入格式", status_code=422)
    if len(keywords) > MAX_BATCH_ITEMS:
        raise BizException(f"单次最多生成 {MAX_BATCH_ITEMS} 篇", status_code=422)

    # ---------- 1. 创建批量任务主记录 ----------
    batch = BatchTask(
        user_id=user_id,
        name=name or f"批量生成 {len(keywords)} 篇",
        platform=platform,
        status=0,  # 排队中
        total=len(keywords),
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    # ---------- 2. 创建明细记录（每篇一行） ----------
    items: list[BatchItem] = []
    for kw in keywords:
        item = BatchItem(batch_id=batch.id, user_id=user_id, keyword=kw, status=0)
        db.add(item)
        items.append(item)
    db.commit()
    # refresh 拿 ID（投递任务需要）
    for item in items:
        db.refresh(item)

    # ---------- 3. 投递 Celery group（每篇一个任务，并发执行） ----------
    batch.status = 1  # 生成中
    db.add(batch)
    db.commit()

    from celery import group

    job = group(
        generate_one.s(item.id, user_id, item.keyword, platform) for item in items
    )
    # 异步投递：不等待结果，worker 消费队列执行
    job.apply_async()
    logger.info("批量任务已投递: batch=%s items=%d", batch.id, len(items))

    return batch


def get_batch(db: Session, user_id: int, batch_id: int) -> BatchTask:
    """查询批量任务（带用户隔离）。"""
    batch = db.scalar(
        select(BatchTask).where(
            BatchTask.id == batch_id, BatchTask.user_id == user_id
        )
    )
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="批量任务不存在"
        )
    return batch


def get_batch_items(db: Session, batch_id: int) -> list[BatchItem]:
    """查询批量任务的所有明细（按 ID 排序）。"""
    stmt = (
        select(BatchItem)
        .where(BatchItem.batch_id == batch_id)
        .order_by(BatchItem.id.asc())
    )
    return list(db.scalars(stmt))


def get_batch_list(db: Session, user_id: int, limit: int = 20) -> list[BatchTask]:
    """查询用户的批量任务列表（最新在前）。"""
    stmt = (
        select(BatchTask)
        .where(BatchTask.user_id == user_id)
        .order_by(BatchTask.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
