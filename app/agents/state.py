"""
LangGraph 状态定义（企业级）

【什么是 State（状态）？】
LangGraph 的核心思想：整个创作流程是一个"状态机"。
所有智能体的输入输出都写在同一个 State（一个字典）里：
- 节点（智能体）从 State 读取自己需要的输入
- 节点处理完，把结果"更新"回 State
- 下一个节点从 State 拿到上一步的结果继续处理

【企业级设计的三个要点】
1. 类型化（TypedDict）：每个字段声明类型，编译期/运行期都能校验
2. Reducer（归约器）：定义"同一字段被多次更新时如何合并"：
   - Annotated[list, operator.add]：新值追加到列表（用于错误收集）
   - 普通字段：直接覆盖（默认行为）
3. 容错字段：errors 收集全流程错误、retry_count 控制重试次数，
   保证任何一步出错都有迹可查、不会无限循环

【字段命名规范】
- 输入字段：keyword/platform/selected_title（用户提供）
- 中间产物：topic/logic_report/draft/polished（各智能体输出）
- 终态字段：final_content/sensitive_report/quality_score（最终结果）
- 元数据：current_step/errors/retry_count/task_id（流程控制）
"""

from typing import Annotated, NotRequired, TypedDict

from langgraph.types import RetryPolicy

# operator.add 作为 reducer：errors 字段每次更新都是"追加"，而不是覆盖
import operator


class CreationState(TypedDict):
    """
    创作流程的状态定义（整个多智能体协作共享的"工作台"）。

    字段按"生命周期"分组：
    1. 初始化注入（图开始前由调用方填入）
    2. 节点产出（各智能体逐步写入）
    3. 流程控制（LangGraph 内部使用）
    """

    # ============ 1. 初始化输入（由 content_service 注入） ============
    keyword: str  # 用户输入的主题/关键词
    platform: str  # 目标平台（小红书/公众号/知乎）
    selected_title: str  # 用户选择的选题标题
    topics: list[dict]  # 选题列表（含完整信息：标题/简介/目标人群/预期效果）
    user_id: int  # 当前用户 ID（落库用）
    task_id: int  # 创作任务 ID（落库用）
    # 内容模板结构要求（可选：用户选了模板时注入，逻辑分析/创作节点读取）
    template_structure: NotRequired[str]

    # ============ 2. 节点产出（各智能体的输出） ============
    topic: dict  # 解析出的用户所选选题（resolve_topic 节点产出）
    logic_report: dict  # 爆文逻辑分析报告（logic_analyzer 节点产出）
    draft: str  # 文案初稿（content_writer 节点产出）
    polished: str  # 润色后文案（polish_agent 节点产出）
    final_content: str  # 最终排版后文案（layout_agent 节点产出）

    # 质量检查结果
    sensitive_report: dict  # 敏感词报告 {"has_sensitive": bool, "words": [...]}
    quality_score: int  # 质量分 0-100

    # ============ 3. 流程控制 ============
    # 当前执行到哪个节点（写日志/落库进度用）
    current_step: NotRequired[str]
    # 重试计数：质量审核不过 → 回润色重写，最多 MAX_RETRIES 次
    # Annotated[int, operator.add]：节点返回 {"retry_count": 1} 时累加
    retry_count: Annotated[int, operator.add]
    # 错误收集：所有节点抛错时追加记录，不会覆盖之前的错误
    errors: Annotated[list[str], operator.add]


# 质量审核重试策略（企业级：指数退避）
# - max_attempts=3：同一节点最多执行 3 次（首次 + 2 次重试）
# - backoff_factor=2.0：重试间隔按 2 倍指数递增（0.5s → 1s → 2s → ...）
# - jitter=True：间隔加随机抖动，避免多任务同时重试打爆上游 API
# - retry_on：仅在特定异常时重试（网络/超时类），业务错误不重试
NODE_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    backoff_factor=2.0,
    jitter=True,
    retry_on=(
        "openai.APITimeoutError",
        "openai.APIConnectionError",
        "openai.InternalServerError",
        "openai.RateLimitError",
    ),
)
