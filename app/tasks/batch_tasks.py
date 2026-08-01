"""
批量内容生成的 Celery 任务

【任务职责】
一个 task = 批量任务里的"一篇"：
1. 标记 batch_item 为生成中
2. 调用 content_service.generate_one_article（跑完整 LangGraph 图）
3. 更新 batch_item 状态（成功关联 task_id / 失败记录原因）
4. 更新 batch_tasks 计数（成功数/失败数），全部完成时标记批量任务完成

【为什么每篇一个 Celery 任务而不是整个批量一个任务？】
- 单篇失败不影响其他篇（每篇独立重试/独立状态）
- 支持并发（threads pool 同时跑多篇）
- 进度粒度细（按篇统计，前端能显示 x/y）
"""

import logging

from app.core.logger import logger
from app.tasks.celery_app import celery_app
@celery_app.task(name="batch.generate_one", bind=True, max_retries=2)
def generate_one(
    self,
    batch_item_id: int,
    user_id: int,
    keyword: str,
    platform: str,
) -> None:
    """
    批量生成单篇（Celery 任务）。

    【重试策略】
    max_retries=2：网络抖动等临时错误时自动重试（最多 3 次执行）。
    注意：重试会导致一篇被生成多次（消耗 API 费用），
    所以只在明确是"临时错误"时重试——生成本身是幂等的（每次覆盖结果）。

    :param batch_item_id: batch_items 表记录 ID
    :param user_id: 用户 ID
    :param keyword: 本篇关键词
    :param platform: 目标平台
    """
    from app.db.session import SessionLocal
    from app.models.batch_task import BatchItem, BatchTask
    from app.services.content_service import generate_one_article

    # 每个任务独立数据库会话（Celery worker 线程间不共享 session）
    db = SessionLocal()
    try:
        # ---------- 1. 标记为生成中 ----------
        item = db.get(BatchItem, batch_item_id)
        if item is None:
            logger.error("批量任务明细不存在: batch_item_id=%s", batch_item_id)
            return
        item.status = 1  # 生成中
        db.add(item)
        db.commit()

        # ---------- 2. 生成单篇（跑完整 LangGraph 图） ----------
        logger.info("批量生成开始: item=%s keyword=%s", batch_item_id, keyword)
        task = generate_one_article(db, user_id, keyword, platform)

        # ---------- 3. 更新明细状态 ----------
        item.status = 2 if task.status == 2 else 3  # 成功/失败
        item.task_id = task.id
        if task.status != 2:
            item.error_message = task.error_message
        db.add(item)
        db.commit()

        # ---------- 4. 更新批量任务计数 ----------
        _update_batch_progress(db, item.batch_id, item.status)
        logger.info("批量单篇完成: item=%s status=%s", batch_item_id, item.status)

    except Exception as exc:
        logger.exception("批量单篇任务异常: item=%s: %s", batch_item_id, exc)
        # 标记失败（不重试：避免无限消耗 API 费用）
        try:
            item = db.get(BatchItem, batch_item_id)
            if item:
                item.status = 3
                item.error_message = str(exc)[:200]
                db.add(item)
                db.commit()
                _update_batch_progress(db, item.batch_id, 3)
        except Exception as inner:
            logger.error("批量失败状态更新异常: %s", inner)
    finally:
        db.close()


def _update_batch_progress(db, batch_id: int, item_status: int) -> None:
    """
    更新批量任务主表的成功/失败计数，全部完成时置为完成态。

    :param db: 数据库会话
    :param batch_id: 批量任务 ID
    :param item_status: 刚完成的单篇状态（2=成功 3=失败）
    """
    from datetime import datetime

    from app.models.batch_task import BatchItem, BatchTask

    batch = db.get(BatchTask, batch_id)
    if batch is None:
        return

    # 重新统计（简单可靠，不依赖增量）
    from sqlalchemy import func, select

    total = db.scalar(select(func.count()).select_from(BatchItem).where(BatchItem.batch_id == batch_id))
    success = db.scalar(
        select(func.count())
        .select_from(BatchItem)
        .where(BatchItem.batch_id == batch_id, BatchItem.status == 2)
    )
    failed = db.scalar(
        select(func.count())
        .select_from(BatchItem)
        .where(BatchItem.batch_id == batch_id, BatchItem.status == 3)
    )

    batch.total = total or 0
    batch.success_count = success or 0
    batch.fail_count = failed or 0
    # 生成中状态计数 = 总数 - 成功 - 失败
    pending = (total or 0) - (success or 0) - (failed or 0)
    if pending == 0:
        # 全部结束：有失败 → 部分失败；全成功 → 完成
        batch.status = 3 if (failed or 0) > 0 else 2
        batch.completed_at = datetime.now()
    else:
        batch.status = 1  # 仍在生成中
    db.add(batch)
    db.commit()
    logger.info("批量进度更新: batch=%s total=%s success=%s fail=%s pending=%s",
                batch_id, batch.total, batch.success_count, batch.fail_count, pending)
