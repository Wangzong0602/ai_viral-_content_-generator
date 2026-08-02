"""
LangGraph 图构建（企业级编排核心）

【这个文件做了什么？】
把 7 个节点（nodes.py）通过"边"连接成一张有向图（DAG），
定义执行顺序、分支条件、重试策略、持久化方式，最终编译成可执行的应用。

【企业级编排设计】
1. 节点注册：每个智能体 = 一个节点（单一职责）
2. 线性边：定义主流程（resolve → logic → writer → polish → layout → quality）
3. 条件边：质量审核不过 → 走重写分支（企业级"审核-修正"闭环）
4. RetryPolicy：每个节点挂载重试策略（网络异常自动指数退避重试）
5. Checkpoint：SQLite 持久化，支持"断点续跑"（进程崩溃后可从上次检查点恢复）

【为什么检查点用 SQLite 而不是 Redis？】
- Redis 方案需要 RedisJSON 模块（JSON.SET 命令），本机 Redis 8.4 社区版未内置
- SQLite 是 LangGraph 官方维护的轻量持久化方案：
  - 单机/单进程场景标准选择（我们当前就是单机部署）
  - 文件持久化，进程重启不丢状态
  - 零外部依赖（Python 内置 sqlite3）
- 如果未来多实例部署需要共享检查点，再切换 Postgres/Redis（接口一致，只改一行）

【图结构示意】
START → resolve_topic → logic_analyzer → content_writer → polish_agent
       → layout_agent → quality_checker ──(通过)──→ END
                                     └──(有敏感词 & 未达上限)──→ revise → quality_checker
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    content_writer_node,
    fact_checker_node,
    layout_agent_node,
    logic_analyzer_node,
    polish_agent_node,
    quality_checker_node,
    resolve_topic_node,
    revise_node,
)
from app.agents.state import NODE_RETRY_POLICY, CreationState

# 敏感词重试上限：同一篇文案最多重写几次（防止无限循环烧钱）
MAX_QUALITY_RETRIES = 2

# 检查点数据库文件路径（项目根目录 /data/checkpoints.sqlite）
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CHECKPOINT_DB = DATA_DIR / "checkpoints.sqlite"


def _should_retry(state: CreationState) -> str:
    """
    质量审核的条件路由函数（条件边的"判断逻辑"）。

    【条件边机制】
    在 add_conditional_edges 里注册本函数，LangGraph 每轮走到
    quality_checker 完成后，会自动调用它，根据返回值选择去向：
    - 返回 "revise"：重写文案（敏感词未清 + 重试次数未达上限）
    - 返回 END：流程结束

    【为什么不在节点里直接返回分支？】
    节点只负责"产出数据"，路由决策交给图的"边"层——职责分离，
    且路径记录在图的拓扑里，可观测、可调试（企业级可审计性）。
    """
    report = state.get("sensitive_report", {})
    has_sensitive = report.get("has_sensitive", False)
    if has_sensitive and state.get("retry_count", 0) < MAX_QUALITY_RETRIES:
        return "revise"
    return "fact_checker"  # 质量通过 → 进入事实核查（方案1）


def build_graph() -> StateGraph:
    """
    构建并编译创作流程图。

    【checkpointer 是什么？】
    检查点 = 每次节点执行完，把 State 快照持久化到 SQLite。
    - 进程崩溃/重启 → 可以从上次检查点恢复（断点续跑）
    - 每任务一个 thread_id（并发用户互不干扰）
    企业级要求：任何状态必须可恢复、可审计。

    【线程安全说明】
    sqlite3.connect(check_same_thread=False)：
    FastAPI 处理并发请求时图可能在不同线程执行，
    SQLite 连接需允许跨线程（SqliteSaver 内部用锁保证线程安全）。
    """
    # ---------- 1. 准备检查点数据库（SQLite 持久化层） ----------
    DATA_DIR.mkdir(parents=True, exist_ok=True)  # 确保 data 目录存在
    conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    # ---------- 2. 创建状态图 ----------
    workflow = StateGraph(CreationState)

    # ---------- 3. 注册节点（每个节点挂载重试策略） ----------
    # retry= 参数：节点执行抛错时，按策略自动重试（指数退避）
    workflow.add_node("resolve_topic", resolve_topic_node, retry=NODE_RETRY_POLICY)
    workflow.add_node("logic_analyzer", logic_analyzer_node, retry=NODE_RETRY_POLICY)
    workflow.add_node("content_writer", content_writer_node, retry=NODE_RETRY_POLICY)
    workflow.add_node("polish_agent", polish_agent_node, retry=NODE_RETRY_POLICY)
    workflow.add_node("layout_agent", layout_agent_node, retry=NODE_RETRY_POLICY)
    workflow.add_node("quality_checker", quality_checker_node, retry=NODE_RETRY_POLICY)
    workflow.add_node("fact_checker", fact_checker_node, retry=NODE_RETRY_POLICY)
    workflow.add_node("revise", revise_node, retry=NODE_RETRY_POLICY)

    # ---------- 4. 连接边（定义主流程） ----------
    workflow.add_edge(START, "resolve_topic")
    workflow.add_edge("resolve_topic", "logic_analyzer")
    workflow.add_edge("logic_analyzer", "content_writer")
    workflow.add_edge("content_writer", "polish_agent")
    workflow.add_edge("polish_agent", "layout_agent")
    workflow.add_edge("layout_agent", "quality_checker")

    # ---------- 5. 条件边（质量审核闭环） ----------
    # quality_checker 完成后调用 _should_retry 决定去向：
    # 有敏感词 → revise 重写；通过 → 进入事实核查（方案1）
    workflow.add_conditional_edges(
        "quality_checker",
        _should_retry,
        {
            "revise": "revise",  # 有敏感词 → 重写
            "fact_checker": "fact_checker",  # 通过 → 事实核查
        },
    )
    # 重写完成后回到 quality_checker 重新审核（形成循环）
    workflow.add_edge("revise", "quality_checker")
    # 事实核查完成后结束
    workflow.add_edge("fact_checker", END)

    # ---------- 6. 编译成可执行应用 ----------
    # checkpointer= 启用持久化；之后调用 app.stream/ainvoke 即可执行
    app = workflow.compile(checkpointer=checkpointer)
    return app


# 模块级单例：整个应用只编译一次图（图结构是不可变配置）
app = build_graph()
