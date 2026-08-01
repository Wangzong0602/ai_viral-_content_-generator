"""
AI 配图接口（异步）

【接口说明】
POST /api/v1/content/images/generate
- 请求体：{"content": 文章, "count": 3, "style": "插画卡通", "task_id": 可选}
- 响应：{"images": [{"url": "/images/...", "scene": "..."}]}
- 需要登录（Bearer Token）
- 返回的 URL 是本地静态资源路径，前端拼接域名即可显示

【记录落库】
生成的配图会写入 image_records 表（关联 task_id），
这样历史记录详情页能展示该文章的配图（之前只返回 URL 没落库的缺陷已修复）。
- 同任务同场景重复生成（换一张）→ 更新原记录
- 未传 task_id → 只保存记录不关联任务
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.logger import logger
from app.db.session import get_db
from app.models.image_record import ImageRecord
from app.models.user import User
from app.schemas.image import ImageGenerateRequest, ImageGenerateResponse, ImageOut
from app.services import image_service

router = APIRouter(prefix="/api/v1/content/images", tags=["AI 配图"])


def _save_image_records(
    db: Session,
    user_id: int,
    task_id: int | None,
    style: str,
    operation: str,
    images: list[dict],
) -> None:
    """
    把生成的配图记录写入数据库（同任务同场景去重更新）。

    :param db: 数据库会话
    :param user_id: 当前用户 ID
    :param task_id: 关联的创作任务 ID（可空）
    :param style: 配图风格
    :param operation: generate / regenerate
    :param images: [{"url": ..., "scene": ...}, ...]
    """
    for img in images:
        scene = img["scene"]
        url = img["url"]
        # 同任务同场景已有记录 → 更新 URL（换一张的效果）
        existing = None
        if task_id:
            existing = db.scalar(
                select(ImageRecord).where(
                    ImageRecord.task_id == task_id,
                    ImageRecord.scene == scene,
                )
            )
        if existing:
            existing.url = url
            existing.style = style
            existing.operation = operation
            db.add(existing)
        else:
            db.add(
                ImageRecord(
                    user_id=user_id,
                    task_id=task_id,
                    url=url,
                    scene=scene,
                    style=style,
                    operation=operation,
                )
            )
    db.commit()
    logger.info("配图记录已保存: %d 张 (task_id=%s)", len(images), task_id)


@router.post("/generate", response_model=ImageGenerateResponse, summary="AI 配图")
async def generate_images(
    data: ImageGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImageGenerateResponse:
    """
    根据文章内容生成配图（语义分析 → 通义万相 → 本地存储 → 记录落库）。

    【operation 说明】
    - generate：常规生成，内部做语义分析提取场景
    - regenerate：前端传 scene 场景描述，直接重新生成该场景的图
      （用户对某张不满意，点"换一张"，保持场景一致）

    :param data: 请求体（content/count/style/operation/scene/task_id）
    :param db: 数据库会话（保存配图记录）
    :param current_user: 当前登录用户（身份保护）
    """
    # 日志记录（用户维度追踪）
    logger.info(
        "用户 %s 请求配图: count=%d style=%s operation=%s task_id=%s",
        current_user.id, data.count, data.style, data.operation, data.task_id,
    )

    if data.operation == "generate":
        # 常规生成：语义分析 + 并发生成
        urls = await image_service.generate_images(
            content=data.content,
            count=data.count,
            style=data.style,
        )
        images = [{"url": url, "scene": f"配图 {i + 1}"} for i, url in enumerate(urls)]
        # 记录落库
        _save_image_records(
            db, current_user.id, data.task_id, data.style, data.operation, images
        )
        return ImageGenerateResponse(images=[ImageOut(**img) for img in images])

    # regenerate：重新生成指定场景（scene 必填）
    if not data.scene:
        from app.core.exceptions import BizException

        raise BizException("regenerate 操作需要提供 scene 参数", status_code=422)

    # 复用语义分析的场景，只重新生成一张
    url = await image_service._generate_one_image(
        scene_prompt=data.scene,
        style_desc=image_service.STYLES.get(data.style, image_service.STYLES["插画卡通"]),
        style_key=data.style,
    )
    images = [{"url": url, "scene": data.scene}]
    # 记录落库（同任务同场景 → 更新原记录）
    _save_image_records(
        db, current_user.id, data.task_id, data.style, data.operation, images
    )
    return ImageGenerateResponse(images=[ImageOut(**img) for img in images])
