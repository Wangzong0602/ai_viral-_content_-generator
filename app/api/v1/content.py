"""
内容创作接口：选题 / SSE 流式生成 / 历史记录

【SSE 是什么？】
SSE = Server-Sent Events（服务器推送事件）。
前端用 EventSource 建立一条"长连接"，服务器可以持续往这条连接推数据。
和 WebSocket 的区别：SSE 是单向的（服务器 → 客户端），
正好适合"AI 生成进度实时展示"这种场景——服务器一直推，前端一直渲染。

【SSE 响应格式】
Content-Type: text/event-stream
每个事件是：
    event: <事件名>
    data: <JSON字符串>

    事件之间用空行分隔。

【前端如何调用（伪代码）】
const es = new EventSource(`/api/v1/content/generate?token=${token}`);
es.addEventListener('progress', e => 更新进度条(JSON.parse(e.data)));
es.addEventListener('content', e => 追加文字(JSON.parse(e.data)));
es.addEventListener('complete', e => 展示最终结果(JSON.parse(e.data)));

【为什么 generate 用 GET + token 参数而不是 POST + Authorization 头？】
EventSource 这个浏览器 API 无法自定义请求头！
所以前端要么把 token 放 URL 参数（本方案，简单），
要么用 fetch 流式读取（更标准但实现复杂）。
MVP 阶段用 URL 参数方案，注意生产环境必须配 HTTPS 防止 token 泄露。
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.content import (
    AdaptItemOut,
    AdaptRequest,
    AdaptResponse,
    AnalyzeReportOut,
    AnalyzeRequest,
    AnalyzeResponse,
    CreateRequest,
    TaskOut,
    TopicsOut,
)
from app.schemas.user import MessageOut
from app.services import adapt_service, analyze_service, content_service

router = APIRouter(prefix="/api/v1/content", tags=["内容创作"])


def _to_task_out(db: Session, task) -> TaskOut:
    """
    把 CreationTask ORM 对象转成 TaskOut，并附加该任务的配图 URL 列表。
    （TaskOut 的 images 字段不能靠 from_attributes 自动填充，需手动查询）
    """
    out = TaskOut.model_validate(task)  # 复用 from_attributes 转换基础字段
    out.images = content_service.get_task_images(db, task.id)
    return out


@router.post("/topics", response_model=TopicsOut, summary="生成爆款选题")
def generate_topics(
    data: CreateRequest,  # 前端传 keyword + platform
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # 需要登录
):
    """
    第一步：根据关键词生成 5 个爆款选题。

    【为什么选题是普通接口而不是 SSE？】
    选题只有 5 个，一次性返回即可，不需要实时进度。
    前端拿到列表后展示给用户，用户点选一个再触发"完整创作"。
    """
    data.validate_platform()  # 校验平台是否支持
    result = content_service.get_topics(data.keyword, data.platform)
    if not result["topics"]:
        # 模型解析失败等异常情况：给前端明确提示而不是空列表
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,  # 502：上游（AI）出错
            detail="选题生成失败，请稍后重试",
        )
    return result


@router.get("/generate", summary="完整创作（SSE 流式）")
def generate(
    keyword: str = Query(..., min_length=1, max_length=200, description="主题/关键词"),
    platform: str = Query(..., description="目标平台"),
    selected_title: str = Query(..., description="用户选择的选题标题"),
    token: str = Query(..., description="JWT 令牌（EventSource 无法带请求头，用 URL 参数）"),
    db: Session = Depends(get_db),
):
    """
    第二步：用户选好选题后，流式生成完整爆文。

    【为什么这里手动校验 token 而不是 Depends(get_current_user)？】
    EventSource 无法自定义请求头（Authorization），token 只能放 URL 参数，
    而 Depends 依赖只能从"请求头"读取。所以这里手动：
    1. 用 token 参数解析出用户身份（复用 deps.py 的校验函数）
    2. 解析失败 → 直接返回 401
    """
    # 复用认证逻辑：通过 token 参数解析出当前用户
    from app.api.deps import get_current_user

    # 由于 get_current_user 依赖请求头，这里用一个轻量包装：
    # 手动构造"只有 token"的认证对象
    from fastapi.security import HTTPAuthorizationCredentials

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=token
    )
    # 这里利用 FastAPI 的依赖系统：手动调用 get_current_user
    # （把 credentials 和 db 都显式传入）
    try:
        current_user = get_current_user(credentials=credentials, db=db)
    except HTTPException as exc:
        # 认证失败：返回和普通接口一致的 401 响应
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        )

    # 校验平台 + 手动构造完整请求对象（get_topics 需要）
    req = CreateRequest(
        keyword=keyword, platform=platform, selected_title=selected_title
    )
    req.validate_platform()

    # 先取一次选题列表（确保 topic 有完整信息：标题/简介/目标人群）
    topics_result = content_service.get_topics(keyword, platform)
    topics = topics_result["topics"]
    if not topics:
        raise HTTPException(status_code=502, detail="选题生成失败，请重试")

    # ---------- 构造 SSE 流式响应 ----------
    def event_stream():
        """
        生成器：把 content_service.stream_generate 的产出
        转换成标准 SSE 格式（event: 事件名 + data: JSON + 空行）。
        """
        for item in content_service.stream_generate(
            db=db,
            user_id=current_user.id,
            keyword=keyword,
            platform=platform,
            selected_title=selected_title,
            topics=topics,
        ):
            event = item["event"]
            data = item["data"]
            # SSE 协议格式：event 行 + data 行 + 空行（用两个 \n 分隔）
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    # StreamingResponse：FastAPI 提供流式响应，直到生成器结束才断开连接
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",  # SSE 的标准媒体类型
        headers={
            # 禁用缓存：流式数据必须实时，不能走浏览器缓存
            "Cache-Control": "no-cache",
            # 不缓冲：让每段数据立即推送到前端（Nginx 等代理也需要配这个）
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tasks", response_model=list[TaskOut], summary="历史记录列表")
def task_list(
    limit: int = Query(default=20, ge=1, le=100, description="返回条数"),
    platform: str | None = Query(default=None, description="按平台筛选"),
    keyword: str | None = Query(default=None, min_length=1, max_length=100, description="按标题/主题搜索"),
    favorite: bool = Query(default=False, description="只看已收藏"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    查看当前用户的生成历史（最新在前，含每篇的配图）。

    【筛选参数（历史记录增强）】
    - platform：只显示指定平台（如 小红书）
    - keyword：标题/主题模糊搜索
    - favorite=true：只看已收藏的
    """
    tasks = content_service.get_task_list(
        db, current_user.id, limit, platform, keyword, favorite
    )
    return [_to_task_out(db, t) for t in tasks]


@router.put("/tasks/{task_id}/favorite", response_model=MessageOut, summary="收藏/取消收藏")
def toggle_favorite(
    task_id: int,
    favorite: bool = Query(default=True, description="true=收藏 false=取消收藏"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    收藏或取消收藏一条历史记录。

    【收藏有什么用？】
    用户生成内容多了以后，把优质内容标记收藏，
    之后在历史记录页勾选"只看收藏"快速找回。
    """
    task = content_service.get_task_detail(db, current_user.id, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="记录不存在",
        )
    task.is_favorite = 1 if favorite else 0
    db.add(task)
    db.commit()
    return {"message": "已收藏" if favorite else "已取消收藏"}


@router.get("/tasks/{task_id}", response_model=TaskOut, summary="历史记录详情")
def task_detail(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    查看单条生成记录详情（含配图）。
    get_task_detail 内部做了 user_id 匹配，别人看不了你的记录。
    """
    task = content_service.get_task_detail(db, current_user.id, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,  # 404：记录不存在
            detail="记录不存在",
        )
    return _to_task_out(db, task)


@router.post("/adapt", response_model=AdaptResponse, summary="一键多平台适配")
async def adapt(
    data: AdaptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdaptResponse:
    """
    把一篇文章改写为多个平台版本（并发生成）。

    【流程】
    1. 校验平台列表（去重 + 是否支持）
    2. adapt_service 并发改写每个平台版本
    3. 返回每个平台的结果（成功的含内容，失败的含错误信息）

    注意：本接口是 async（内部用 asyncio.gather 并发调用大模型）。
    """
    data.validate_platforms()  # 校验 + 去重
    results = await adapt_service.adapt_content(data.content, data.platforms)
    return AdaptResponse(
        results=[AdaptItemOut(**r) for r in results]
    )


@router.delete("/tasks/{task_id}", response_model=MessageOut, summary="删除历史记录")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除单条历史记录（软删除：status 改为 3）。

    【为什么软删除而不是物理删除？】
    与用户注销同理（见 user.py）：记录虽然对用户不可见，
    但保留在库里便于数据统计和审计（P2 数据看板会用到）。
    """
    task = content_service.get_task_detail(db, current_user.id, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="记录不存在",
        )
    task.status = 3  # 已删除（与用户注销的状态值一致）
    db.add(task)
    db.commit()
    return {"message": "记录已删除"}


@router.post("/analyze", response_model=AnalyzeResponse, summary="爆文逆向分析")
async def analyze(
    data: AnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyzeResponse:
    """
    逆向分析一篇爆文（学习功能）。

    【输入方式】
    - 链接：input_text 填文章 URL → 服务端抓取网页提取正文
    - 内容：input_text 直接粘贴文章全文

    【输出】
    拆解报告：标题钩子 / 开头3秒 / 内容结构 / 情绪价值 / 行动召唤 / SEO关键词 / 总体方法论

    【async 说明】
    内部包含网络抓取（httpx async）和大模型调用（线程池），不阻塞事件循环。
    """
    result = await analyze_service.analyze_viral_article(data.input_text)
    return AnalyzeResponse(
        title=result["title"],
        content_len=result["content_len"],
        report=AnalyzeReportOut(**result["report"]),
    )
