"""
内容创作服务：通过 LangGraph 状态机驱动完整创作流水线

【本文件做了什么？】
1. 生成选题（get_topics）：第一步，只调选题智能体（不进入状态机）
2. 完整创作（stream_generate）：把用户输入注入 LangGraph 状态，
   用 app.stream 执行整张图（7 个节点），并把图产出的流式事件
   转换成前端 SSE 格式逐段推送
3. 历史记录管理（列表/详情）

【LangGraph 如何驱动 SSE？】
app.stream(input_state, config, stream_mode=["custom", "updates"]) 会产出两种数据：
- ("custom", chunk)：节点内 StreamWriter 推送的增量文本（正文打字机效果）
- ("updates", {node_name: {...}})：某节点执行完后的状态更新（进度事件）
我们把这个二元组流映射成 SSE 事件：
  ("custom", chunk)      → {"event": "content", "data": chunk}
  ("updates", {...})     → {"event": "progress", "data": {...}}

【config 里的 thread_id 是什么？】
LangGraph 检查点（checkpoint）的"会话标识"：
- 每次生成用唯一 thread_id（如 f"task-{task_id}"）
- Redis 按 thread_id 保存每一节点的状态快照
- 好处：进程崩溃后可断点续跑；不同用户的生成互不干扰

【get_state 是什么？】
图执行结束后，调用 app.get_state(config) 从检查点读取"最终状态"，
拿到 final_content/sensitive_report/quality_score 等终态数据落库。
"""

import json
from datetime import datetime

from langgraph.graph import END
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.agents import topic_agent
from app.agents.graph import app  # 编译好的 LangGraph 应用（全局单例）
from app.core.exceptions import BizException
from app.core.logger import logger
from app.models.creation_task import CreationTask
from app.models.image_record import ImageRecord

# 节点名 → 中文步骤名映射（前端进度条展示用）
NODE_NAMES = {
    "resolve_topic": "选题解析",
    "logic_analyzer": "爆文逻辑分析",
    "content_writer": "文案创作",
    "polish_agent": "润色优化",
    "layout_agent": "排版整合",
    "quality_checker": "质量审核",
    "revise": "敏感词重写",
}


def get_topics(keyword: str, platform: str, template_structure: str = "") -> dict:
    """
    第一步：根据关键词生成 5 个爆款选题。

    选题生成是"独立的交互步骤"（用户要先选择），
    不进入 LangGraph 状态机（状态机从"选题已确定"开始跑）。

    :param keyword: 主题/关键词
    :param platform: 目标平台
    :param template_structure: 内容模板结构要求（可选）
    """
    topics = topic_agent.generate_topics(keyword, platform, template_structure)
    return {"keyword": keyword, "platform": platform, "topics": topics}


def _get_template_structure(db: Session, template_id: int | None) -> str:
    """
    根据模板 ID 获取结构要求文本（JSON 转可读文本）。

    :param db: 数据库会话
    :param template_id: 模板 ID（可选）
    :return: 模板结构描述文本（无模板时返回空串）
    """
    if not template_id:
        return ""
    from app.services.template_service import get_template

    template = get_template(db, template_id)
    if not template:
        return ""
    try:
        structure = json.loads(template.structure or "{}")
    except json.JSONDecodeError:
        return ""
    # 转成可读文本（hook/opening/body/cta）
    parts = []
    labels = {"hook": "标题钩子", "opening": "开头", "body": "正文结构", "cta": "结尾行动召唤"}
    for key, label in labels.items():
        if structure.get(key):
            parts.append(f"{label}：{structure[key]}")
    return "\n".join(parts)


def _make_progress(node_name: str, status: str, detail: str = "") -> dict:
    """构造 progress 事件字典（前端进度条）。"""
    return {
        "event": "progress",
        "data": {
            "step": node_name,
            "step_name": NODE_NAMES.get(node_name, node_name),
            "status": status,
            "detail": detail,
        },
    }


def stream_generate(
    db: Session,
    user_id: int,
    keyword: str,
    platform: str,
    selected_title: str,
    topics: list[dict],
    template_id: int | None = None,
):
    """
    完整创作流水线（生成器）：LangGraph 状态机执行 + SSE 事件输出。

    【执行流程】
    1. 创建数据库任务记录（status=1 生成中）
    2. 构造 LangGraph 初始状态（输入字段注入）
    3. app.stream 执行整张图：
       - updates → 推送 progress 事件 + 更新 DB 进度
       - custom  → 推送 content 事件（实时正文）
    4. 图执行完毕 → get_state 读取终态 → 落库（status=2 完成）
    5. 异常 → 落库（status=3 失败）+ 推送 error 事件

    :yield: SSE 事件字典（progress/content/complete/error）
    """
    # ---------- 1. 创建任务记录 ----------
    task = CreationTask(
        user_id=user_id,
        keyword=keyword,
        platform=platform,
        selected_title=selected_title,
        status=1,  # 生成中
        current_step="init",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # thread_id：每个任务一个唯一会话 ID（检查点隔离 + 断点续跑基础）
    config = {"configurable": {"thread_id": f"task-{task.id}"}}

    # 模板结构注入（用户选了模板时生效）
    template_structure = _get_template_structure(db, template_id)

    # ---------- 2. 构造初始状态（图输入） ----------
    initial_state = {
        "keyword": keyword,
        "platform": platform,
        "selected_title": selected_title,
        "topics": topics,
        "user_id": user_id,
        "task_id": task.id,
        "retry_count": 0,  # 重试计数从 0 开始
        "template_structure": template_structure,  # 模板结构（可为空串）
    }

    try:
        # ---------- 3. 执行图（stream_mode 双通道） ----------
        # last_node：记录最后一个执行完的节点（get_state 之前能知道走到哪）
        last_updates: dict = {}
        for mode, payload in app.stream(
            initial_state,
            config=config,
            stream_mode=["custom", "updates"],
        ):
            if mode == "custom":
                # ---------- 3a. 流式正文 ----------
                # 节点内 writer(chunk) 的产出，直接推给前端
                yield {"event": "content", "data": payload}
            elif mode == "updates":
                # ---------- 3b. 节点完成事件 ----------
                # payload = {node_name: {state 更新}}，通常只有一个节点
                last_updates = payload
                for node_name, update in payload.items():
                    # 推送开始事件（带当前步骤信息）
                    detail = ""
                    # 敏感词重写时附带当前重试轮次
                    if node_name == "revise":
                        detail = f"第 {update.get('retry_count', 1)} 次重写"
                    yield _make_progress(node_name, "done", detail)

                    # 同步更新 DB 进度字段（用户中途离开也能看到进度）
                    task.current_step = node_name
                    db.add(task)
                    db.commit()

        # ---------- 4. 读取终态并落库 ----------
        final_state = app.get_state(config).values
        content = final_state.get("final_content", "")
        report = final_state.get("sensitive_report", {})
        score = final_state.get("quality_score", 0)
        retries = final_state.get("retry_count", 0)

        task.status = 2  # 已完成
        task.content = content
        task.quality_score = score
        task.sensitive_report = json.dumps(report, ensure_ascii=False)
        task.completed_at = datetime.now()
        db.add(task)
        db.commit()
        db.refresh(task)

        # 完成事件：带最终结果（前端渲染全文）
        yield {
            "event": "complete",
            "data": {
                "task_id": task.id,
                "title": final_state.get("topic", {}).get("title", selected_title),
                "content": content,
                "sensitive_report": report,
                "quality_score": score,
                "retry_count": retries,
            },
        }

    except Exception as exc:
        # ---------- 兜底：任何节点报错（含重试耗尽）都在这里 ----------
        task.status = 3  # 失败
        task.error_message = str(exc)[:200]
        db.add(task)
        db.commit()
        yield {"event": "error", "data": {"detail": f"生成失败：{exc}"}}


def get_task_list(
    db: Session,
    user_id: int,
    limit: int = 20,
    platform: str | None = None,
    keyword: str | None = None,
    favorite_only: bool = False,
) -> list[CreationTask]:
    """
    查询当前用户的历史生成记录（按时间倒序，不含已删除的）。

    【筛选条件（历史记录增强）】
    - platform：按平台过滤（如"小红书"）
    - keyword：标题/关键词模糊搜索（LIKE）
    - favorite_only：只看已收藏

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param limit: 返回条数上限
    :param platform: 平台筛选（可选）
    :param keyword: 搜索关键词（可选，匹配标题或主题词）
    :param favorite_only: 只看收藏（可选）
    """
    stmt = (
        select(CreationTask)
        .where(CreationTask.user_id == user_id)
        .where(CreationTask.status != 3)  # 排除已删除（软删除）
    )
    # 平台筛选
    if platform:
        stmt = stmt.where(CreationTask.platform == platform)
    # 关键词搜索（标题 或 主题词 LIKE）
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(CreationTask.selected_title.like(like), CreationTask.keyword.like(like))
        )
    # 只看收藏
    if favorite_only:
        stmt = stmt.where(CreationTask.is_favorite == 1)

    stmt = stmt.order_by(CreationTask.created_at.desc()).limit(limit)
    return list(db.scalars(stmt))


def get_task_detail(db: Session, user_id: int, task_id: int) -> CreationTask | None:
    """查询单条记录详情（带用户隔离 + 排除已删除：只能查自己的、未删除的）。"""
    stmt = select(CreationTask).where(
        CreationTask.id == task_id,
        CreationTask.user_id == user_id,
        CreationTask.status != 3,
    )
    return db.scalar(stmt)


def get_task_images(db: Session, task_id: int) -> list[str]:
    """
    查询某任务关联的配图 URL 列表（按创建时间排序）。

    :param db: 数据库会话
    :param task_id: 创作任务 ID
    :return: 图片 URL 列表（可能为空）
    """
    stmt = (
        select(ImageRecord.url)
        .where(ImageRecord.task_id == task_id)
        .order_by(ImageRecord.created_at.asc())
    )
    return list(db.scalars(stmt))


def generate_one_article(db: Session, user_id: int, keyword: str, platform: str) -> CreationTask:
    """
    批量任务用的单篇生成（非流式，直接跑完 LangGraph 整张图）。

    【与 stream_generate 的区别】
    - stream_generate：流式（SSE 逐段推送），用于交互式创作
    - generate_one_article：一次性跑完，返回最终结果，用于后台批量任务

    【执行流程】
    1. 生成选题（自动取第一个，批量场景不需要用户选择）
    2. 初始化 LangGraph 状态 → app.invoke 跑完整张图（非流式）
    3. 落库 creation_tasks（与交互式创作共用历史记录）

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param keyword: 本篇关键词
    :param platform: 目标平台
    :return: 已落库的 CreationTask（status=2 成功 / 3 失败，带 error_message）
    """
    # ---------- 1. 创建任务记录 ----------
    task = CreationTask(
        user_id=user_id,
        keyword=keyword,
        platform=platform,
        selected_title=keyword,  # 批量场景：用关键词作为初始标题（选题生成后覆盖）
        status=1,
        current_step="init",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        # ---------- 2. 生成选题（自动取第一个） ----------
        topics = topic_agent.generate_topics(keyword, platform)
        if not topics:
            raise BizException("选题生成失败", status_code=502)
        topic = topics[0]

        # ---------- 3. 初始化 LangGraph 状态并整图执行 ----------
        config = {"configurable": {"thread_id": f"batch-task-{task.id}"}}
        initial_state = {
            "keyword": keyword,
            "platform": platform,
            "selected_title": topic.get("title", keyword),
            "topics": topics,
            "user_id": user_id,
            "task_id": task.id,
            "retry_count": 0,
        }
        # invoke：一次性跑完所有节点（阻塞直到结束，返回最终状态）
        final_state = app.invoke(initial_state, config=config)

        # ---------- 4. 读取终态并落库 ----------
        content = final_state.get("final_content", "")
        if not content:
            raise BizException("生成内容为空", status_code=502)

        task.status = 2
        task.selected_title = final_state.get("topic", {}).get("title", keyword)
        task.content = content
        task.quality_score = final_state.get("quality_score", 0)
        task.sensitive_report = json.dumps(
            final_state.get("sensitive_report", {}), ensure_ascii=False
        )
        task.completed_at = datetime.now()
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    except Exception as exc:
        # 任何环节失败：标记失败并记录原因（批量任务继续跑下一篇）
        logger.error("批量单篇生成失败 keyword=%s: %s", keyword, exc)
        task.status = 3
        task.error_message = str(exc)[:200]
        db.add(task)
        db.commit()
        return task
