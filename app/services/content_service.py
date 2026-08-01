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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import topic_agent
from app.agents.graph import app  # 编译好的 LangGraph 应用（全局单例）
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


def get_topics(keyword: str, platform: str) -> dict:
    """
    第一步：根据关键词生成 5 个爆款选题。

    选题生成是"独立的交互步骤"（用户要先选择），
    不进入 LangGraph 状态机（状态机从"选题已确定"开始跑）。
    """
    topics = topic_agent.generate_topics(keyword, platform)
    return {"keyword": keyword, "platform": platform, "topics": topics}


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

    # ---------- 2. 构造初始状态（图输入） ----------
    initial_state = {
        "keyword": keyword,
        "platform": platform,
        "selected_title": selected_title,
        "topics": topics,
        "user_id": user_id,
        "task_id": task.id,
        "retry_count": 0,  # 重试计数从 0 开始
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


def get_task_list(db: Session, user_id: int, limit: int = 20) -> list[CreationTask]:
    """查询当前用户的历史生成记录（按时间倒序，不含已删除的）。"""
    stmt = (
        select(CreationTask)
        .where(CreationTask.user_id == user_id)
        .where(CreationTask.status != 3)  # 排除已删除（软删除）
        .order_by(CreationTask.created_at.desc())
        .limit(limit)
    )
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
