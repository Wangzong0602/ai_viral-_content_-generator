"""
AI 配图接口（异步）

【接口说明】
POST /api/v1/content/images/generate
- 请求体：{"content": 文章, "count": 3, "style": "插画卡通"}
- 响应：{"images": [{"url": "/images/...", "scene": "..."}]}
- 需要登录（Bearer Token）
- 返回的 URL 是本地静态资源路径，前端拼接域名即可显示

【异步规范】
- async def 端点（不阻塞事件循环）
- 耗时操作（AI 调用/下载）全部走 asyncio.to_thread / httpx async
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.logger import logger
from app.db.session import get_db
from app.models.user import User
from app.schemas.image import ImageGenerateRequest, ImageGenerateResponse, ImageOut
from app.services import image_service

router = APIRouter(prefix="/api/v1/content/images", tags=["AI 配图"])


@router.post("/generate", response_model=ImageGenerateResponse, summary="AI 配图")
async def generate_images(
    data: ImageGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImageGenerateResponse:
    """
    根据文章内容生成配图（语义分析 → 通义万相 → 本地存储）。

    【operation 说明】
    - generate：常规生成，内部做语义分析提取场景
    - regenerate：前端传 scene 场景描述，直接重新生成该场景的图
      （用户对某张不满意，点"换一张"，保持场景一致）

    :param data: 请求体（content/count/style/operation/scene）
    :param db: 数据库会话（当前为占位，后续配图记录落库时使用）
    :param current_user: 当前登录用户（身份保护）
    """
    # 日志记录（用户维度追踪）
    logger.info(
        "用户 %s 请求配图: count=%d style=%s operation=%s",
        current_user.id, data.count, data.style, data.operation,
    )

    if data.operation == "generate":
        # 常规生成：语义分析 + 并发生成
        urls = await image_service.generate_images(
            content=data.content,
            count=data.count,
            style=data.style,
        )
        return ImageGenerateResponse(
            images=[ImageOut(url=url, scene=f"配图 {i + 1}") for i, url in enumerate(urls)]
        )

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
    return ImageGenerateResponse(
        images=[ImageOut(url=url, scene=data.scene)]
    )
