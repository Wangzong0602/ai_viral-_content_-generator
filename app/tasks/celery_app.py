"""
Celery 异步任务队列配置

【用途】
批量内容生成的异步执行：把"生成一篇"的任务投递到队列，
worker 进程消费队列逐篇生成（支持并发），
主应用（FastAPI）不被长任务阻塞。

【为什么用 threads pool？】
Celery 默认 prefork 池在 Windows 上不支持（fork 是 Unix 特性）。
Windows 下必须指定 pool=threads（或 solo）：
- threads：多线程并发（GIL 下对 IO 密集型任务（AI API 调用）足够）
- 启动 worker：celery -A app.tasks.celery_app worker --pool=threads

【任务定义】
任务在 app/tasks/batch_tasks.py 中通过 @celery_app.task 装饰器注册。

【Redis 队列】
broker：redis://127.0.0.1:16379/1（与项目 Redis 同实例，用 1 号库隔离）
backend：结果存储（当前不需要存任务结果，可省）
"""

from celery import Celery

from app.core.config import settings

# 创建 Celery 实例
# - broker：任务队列（Redis）
# - include：注册的任务模块（自动导入）
celery_app = Celery(
    "ai_content_generator",
    broker=settings.REDIS_URL.replace("/0", "/1"),  # 用 Redis 1 号库做队列，与缓存/会话隔离
    include=["app.tasks.batch_tasks"],
)

# 任务配置
celery_app.conf.update(
    # 任务执行超时：单篇生成最长 5 分钟（AI 调用可能较慢）
    task_time_limit=300,
    # 任务软超时：4 分钟后触发 SoftTimeLimitExceeded
    task_soft_time_limit=240,
    # 任务结果不保存（进度在数据库/Redis 里维护）
    task_ignore_result=True,
    # 消息持久化：worker 重启不丢任务
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
