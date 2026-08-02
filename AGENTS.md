# AI 爆文智能创作平台 - 项目开发指南（AGENTS.md）

> 本文件供 AI 助手（opencode）和开发者读取，新会话启动时自动加载。
> 目标是：**即使没有前文上下文，也能立即了解项目并继续开发。**

## 项目简介

面向自媒体创作者的 AI 爆文生成 SaaS 平台：输入关键词 → AI 多智能体协作生成爆文
（选题→爆文逻辑分析→文案创作→润色→排版→质量审核→事实核查）→ 配图/多平台适配/批量生成。

## 技术栈

- **后端**：Python 3.12（conda 环境 `fastapi_env`，路径 `E:\miniconda3\envs\fastapi_env\python.exe`）
  FastAPI + SQLAlchemy 2.0 + MySQL + Redis + Celery + LangGraph + 通义千问/DashScope
- **前端**：Vue 3 + Vite + Pinia + Vue Router + Element Plus + ECharts + Axios
- **模型**：通义千问 qwen-plus（文本，支持 enable_search 联网搜索）、
  wan2.7-image-pro（配图）、deepseek-v4-flash（默认 DASHSCOPE_MODEL，长文本 JSON 输出不可靠）

## 目录结构（app/）

```
app/
├── agents/          # AI 智能体（LangGraph）
│   ├── graph.py     # LangGraph 状态机编排（节点/条件边/checkpoint）
│   ├── nodes.py     # 图节点（选题解析/逻辑分析/创作/润色/排版/质检/事实核查/重写）
│   ├── state.py     # 状态定义（含 template_structure/fact_context/fact_check_report）
│   ├── topic_agent.py / logic_analyzer.py / content_writer.py / polish_agent.py / layout_agent.py
│   └── viral_analyzer.py  # 爆文逆向分析
├── api/
│   ├── deps.py      # JWT + Redis 会话认证
│   ├── admin_deps.py# 管理员权限（is_admin==1）
│   └── v1/          # auth/user/content(创作+历史)/image(配图)/batch(批量)/dashboard/template/admin
├── core/
│   ├── config.py    # 配置（读 .env）
│   ├── security.py  # bcrypt + JWT
│   ├── logger.py    # 统一日志（logs/app.log）
│   └── exceptions.py# BizException + 全局异常处理器
├── db/session.py    # SQLAlchemy 会话
├── models/          # user/creation_task/image_record/batch_task/content_template
├── schemas/         # Pydantic v2
├── services/        # 业务逻辑（含 ai_service/adapt/fact_check/template 等）
├── tasks/           # Celery（celery_app.py + batch_tasks.py）
├── static/swagger/  # 本地 Swagger UI 资源
├── init_db.py       # 建表：python -m app.init_db
└── main.py          # 应用入口
```

## 服务启动（重要）

```powershell
# 1. Redis（端口 16379！系统排除了 6379）
Start-Process "D:\Redis\redis\redis-server.exe" -ArgumentList "--port","16379","--bind","127.0.0.1","--save","`"`"","--appendonly","no" -WorkingDirectory "D:\Redis\redis" -WindowStyle Hidden

# 2. Celery worker（批量生成必需，Windows 用 threads 池）
Start-Process "E:\miniconda3\envs\fastapi_env\python.exe" -ArgumentList "-m","celery","-A","app.tasks.celery_app","worker","--pool=threads","--concurrency=2","-l","info" -WorkingDirectory "D:\my_project\ai_viral _content_ generator" -WindowStyle Hidden

# 3. 后端（8001 端口，8000 被 C-Lodop 占用）
Start-Process "E:\miniconda3\envs\fastapi_env\python.exe" -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8001" -WorkingDirectory "D:\my_project\ai_viral _content_ generator" -WindowStyle Hidden

# 4. 前端（8002 端口，5173/5454 被系统排除范围占用）
Start-Process "D:\node.js\npm.cmd" -ArgumentList "run","dev" -WorkingDirectory "D:\my_project\ai_viral _content_ generator\frontend" -WindowStyle Hidden
```

访问：前端 http://127.0.0.1:8002 / API 文档 http://127.0.0.1:8001/docs
也可双击 `start_dev.bat`（Redis+Celery+后端）。

## 关键账号与配置

- **管理员**：19900000001 / admin123456（后台管理 /admin 页面）
- **数据库**：MySQL root/010819，库名 `ai_content_generator`（utf8mb4）
- **Redis**：127.0.0.1:16379（0 库会话，1 库 Celery 队列）
- **.env**：DASHSCOPE_API_KEY（通义千问）、数据库/Redis/JWT 配置（已 gitignore）
- **SQLite 检查点**：`data/checkpoints.sqlite`（LangGraph 持久化）

## 开发规范（必须遵守）

1. **数据安全（最高优先级）**：禁止无条件 DELETE/TRUNCATE 全表！
   - 测试账号统一用 199 号段手机号；清理只用 `clean_test_data.py`（只删 199 号段且非管理员）
   - 删除数据前先备份；真实用户数据（非 199）视为不可删
2. **代码规范**：async 异步、类型注解、Pydantic v2 校验、BizException+全局异常处理器（不裸 raise）、
   logger 不用 print、配置全走 .env
3. **模型注意**：事实核查/联网搜索必须用 `qwen-plus`（deepseek-v4-flash 长文本 JSON 会返回空）；
   enable_search 必须是 DashScope 原生 SDK 顶层参数（OpenAI 兼容模式不生效）
4. **端口**：后端 8001、前端 8002（5173/5454/6379 在系统排除范围）
5. **前端测试**：`frontend/scripts/` 下用 Playwright（chrome channel）验证，
   `node scripts/xxx.cjs` 运行；真实登录表单优先于手动 set localStorage（有时序问题）

## 已知技术要点

- LangGraph 图：nodes 含 fact_checker（质量通过后执行事实核查），条件边 quality→revise/fact_checker
- SSE 流式：EventSource 无法带请求头，token 走 URL 参数（/content/generate?token=）
- 选题两步分离：/content/topics 生成 5 选题 → 用户选择 → /content/generate
- 多平台：首屏多选（multiPlatforms）→ 主版本完成后自动 adapt
- 事实保障三方案：创作前搜索注入 + LangGraph 核查节点 + 前端风险警告条
- 批量生成：Celery threads pool，每篇一个任务，进度入 batch_items/tasks

## Git 状态（重开会话时确认）

- 远程：https://github.com/Wangzong0602/ai_viral-_content_-generator.git
- 注意：本地可能领先远程 1 个提交（GitHub 网络不稳，push 失败需重试）
- 备份分支：`backup/visual-refactor`（视觉重构）、`backup/ui-optimize-7b9a447`（ui-ux 优化）
- 提交规范：feat:/fix:/style:/chore: + 中文描述

## 下一步建议（按优先级）

1. 完成 `d8d46f8` 的 push（GitHub 网络恢复后）
2. P3 扩展：开放 API / 多内容形态（视频脚本）/ 更多平台 / 国际化
3. 或会员与支付系统（需微信/支付宝商户资质）
4. 或前端视觉打磨（参考 backup/ui-optimize-7b9a447，但上次导致布局问题，需谨慎）
