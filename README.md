# AI 爆文智能创作平台

> **项目定位**：面向自媒体创作者的多智能体协作 + 多模态内容生成 SaaS 平台  
> **技术含金量**：LangGraph 智能体编排 + FastAPI 异步架构 + SSE 流式输出 + 多模态融合  
> **商业价值**：解决真实行业痛点，可直接商业化落地的完整产品

---

## 项目简介

AI 爆文智能创作平台是一个面向小红书、知乎、公众号、抖音等平台的自媒体创作者，通过「多智能体协作 + 多模态生成」全自动完成选题、爆文逻辑分析、文案写作、润色、SEO优化、AI配图、排版、导出的完整创作流程。

解决创作者：**选题难、爆文逻辑不会、写作慢、配图烦、排版累、内容不涨粉** 的真实行业痛点。

---

## 核心功能

### 🎯 全自动爆文创作（核心功能）
- **智能选题**：输入关键词，AI 生成 5 个爆款选题方向
- **爆文逻辑分析**：拆解平台推荐机制 + 用户心理 + 热点趋势
- **文案创作**：AI 生成初稿（标题 + 正文 + 结尾）
- **润色优化**：优化语言表达、增强情绪价值
- **SEO 优化**：优化关键词密度、添加话题标签
- **AI 配图**：根据内容语义自动生成 3-5 张配图
- **排版整合**：根据平台风格自动排版（小红书/知乎/公众号/抖音）
- **质量审核**：检查敏感词、逻辑错误、格式问题

### 📊 爆文逆向分析
- 输入爆文链接/内容，AI 自动分析爆文要素
- 学习爆文标题钩子、开头 3 秒、情绪价值点、SEO 关键词

### 🔄 一键多平台适配
- 同一篇内容，一键生成小红书/知乎/公众号/抖音版本
- 自动适配不同平台的风格和格式要求

### 📦 批量内容生成
- 上传选题表（Excel/CSV），批量生成 30 篇文章
- 适合 MCN 机构、内容工作室

---

## 技术架构

### 技术栈

#### 后端
- **Python 3.11+** - 编程语言
- **FastAPI** - Web 框架
- **LangGraph** - 智能体协作框架
- **SQLAlchemy** - ORM 框架
- **Redis + Celery** - 异步任务队列
- **MySQL** - 主数据库
- **阿里云 OSS** - 文件存储

#### 前端
- **Vue 3** - 前端框架
- **Vite** - 构建工具
- **Pinia** - 状态管理
- **Element Plus** - UI 组件库
- **TailwindCSS** - CSS 框架

#### AI 模型
- **通义千问** - 文本生成模型
- **通义万相** - 图像生成模型

### 核心技术亮点

1. **多智能体协作架构**：8 个专业智能体分工协作
   - 选题智能体
   - 爆文逻辑分析智能体
   - 文案创作智能体
   - 润色优化智能体
   - SEO 优化智能体
   - 多模态配图智能体
   - 排版整合智能体
   - 质量审核智能体

2. **LangGraph 状态机编排**：流程清晰、可视化、易扩展

3. **SSE 流式输出**：实时展示每个智能体的工作进度

4. **多模态融合**：文本 + 图像一站式生成

5. **平台适配策略**：不同平台不同风格模板

---

## 项目结构

```
ai_viral_content_generator/
├── app/                     # 后端代码
│   ├── agents/              # AI 智能体
│   │   ├── topic_agent.py       # 选题智能体
│   │   ├── logic_analyzer.py    # 爆文逻辑分析智能体
│   │   ├── content_writer.py    # 文案创作智能体
│   │   ├── polish_agent.py      # 润色优化智能体
│   │   ├── layout_agent.py      # 排版整合智能体
│   │   └── base.py              # 公共工具（JSON 解析）
│   ├── api/
│   │   ├── v1/
│   │   │   ├── auth.py     # 注册/登录/登出/获取当前用户
│   │   │   ├── user.py     # 修改资料/修改密码/注销账号
│   │   │   └── content.py  # 选题/SSE流式创作/历史记录
│   │   └── deps.py         # 当前用户依赖（JWT + Redis 会话校验）
│   ├── core/
│   │   ├── config.py       # 配置（pydantic-settings）
│   │   └── security.py     # bcrypt 密码哈希 + JWT
│   ├── db/
│   │   └── session.py      # SQLAlchemy 会话
│   ├── models/
│   │   ├── user.py         # 用户模型
│   │   └── creation_task.py# 创作任务模型（历史记录）
│   ├── schemas/
│   │   ├── user.py         # 用户请求/响应模型
│   │   └── content.py      # 创作请求/响应模型
│   ├── services/
│   │   ├── session.py      # Redis 会话存储
│   │   ├── user_service.py # 用户业务逻辑
│   │   ├── content_service.py # 创作流水线编排（多智能体串联）
│   │   ├── ai_service.py   # 通义千问 API 封装
│   │   └── sensitive_words.py # 敏感词检查
│   ├── init_db.py          # 数据库表初始化
│   └── main.py             # 入口文件
├── .env                    # 环境变量
├── start_dev.bat           # 一键启动脚本
├── test_main.http          # HTTP 接口测试
├── test_user_module.py     # 用户模块自动化测试
├── test_content_module.py  # 创作模块自动化测试
└── README.md               # 项目说明
```

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- MySQL 8.0+
- Redis 5.0+

### 后端启动

```bash
# 1. 配置环境变量（数据库 / Redis 连接信息）
cp .env.example .env
# 编辑 .env 文件，填入数据库、Redis 连接信息

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化数据库表
python -m app.init_db

# 4. 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

> Windows 可直接双击运行 `start_dev.bat`（自动启动 Redis + FastAPI）。
> API 文档：http://127.0.0.1:8001/docs

### 用户管理模块（已实现）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/auth/register` | POST | 注册（手机号 + 密码），返回 Token + 用户信息 |
| `/api/v1/auth/login` | POST | 登录（手机号/邮箱 + 密码），返回 Token + 用户信息 |
| `/api/v1/auth/logout` | POST | 登出（销毁 Redis 会话） |
| `/api/v1/auth/me` | GET | 获取当前用户信息（需 Bearer Token） |
| `/api/v1/user/profile` | PUT | 修改昵称 / 头像 / 简介 |
| `/api/v1/user/password` | PUT | 修改密码 |
| `/api/v1/user/account` | DELETE | 注销账号 |

> 认证方式：JWT（Bearer Token）+ Redis 会话双重校验，登出后 Token 立即失效。

### 内容创作模块（已实现）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/content/topics` | POST | 输入关键词生成 5 个爆款选题 |
| `/api/v1/content/generate` | GET | SSE 流式完整创作（逻辑分析→创作→润色→排版→质检） |
| `/api/v1/content/tasks` | GET | 历史记录列表 |
| `/api/v1/content/tasks/{id}` | GET | 历史记录详情 |

> **创作流水线（LangGraph 状态机编排）**：
> 选题解析 → 爆文逻辑分析 → 文案创作（流式）→ 润色优化（流式）→ 排版整合 → 质量审核
> └── 质量审核不过 → 敏感词重写 → 重新审核（最多 2 轮，条件边控制）
> **企业级特性**：节点级重试（指数退避）、SQLite 检查点持久化（断点续跑）、
> 条件路由（审核-修正闭环）、StreamWriter 自定义流式通道。
> **模型**：通义千问 qwen-plus（阿里云 DashScope，兼容 OpenAI 协议）。
> **注意**：`/generate` 使用 SSE 流式协议，浏览器 EventSource 无法带请求头，需把 token 放 URL 参数（如 `?token=xxx`）。

### 前端启动

```bash
# 1. 安装依赖
cd frontend
npm install

# 2. 启动开发服务器
npm run dev
```

访问：http://127.0.0.1:8002

> 端口说明：5173/5454 都在 Windows 系统排除范围内无法绑定（该范围动态变化），当前使用 8002。

### 前端页面（已实现）

| 页面 | 路由 | 说明 |
|------|------|------|
| 登录 / 注册 | `/login` `/register` | 注册成功自动登录进入工作台 |
| 创作工作台 | `/` | 输入主题+选平台 → 一键生成（两步合一：自动采用第 1 个选题）→ SSE 实时进度+打字机 → 结果编辑/复制/导出 Markdown/纯文本 → **AI 配图**（风格可选/单张换图/点击预览） |
| 历史记录 | `/history` | 列表/详情/复用（带参数跳转工作台自动生成） |

> 技术栈：Vue3 + Vite + Pinia + Vue Router + Element Plus + Axios。
> SSE 使用浏览器原生 EventSource（无法带请求头，token 走 URL 参数）。
> 开发代理：`/api`、`/images` 请求自动转发到后端 8001 端口（vite.config.js）。

### AI 配图模块（已实现）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/content/images/generate` | POST | 语义分析→通义万相生成→本地存储，返回本地 URL 列表 |

- **流程**：通义千问语义分析提取配图场景 → 通义万相（wanx2.1-t2i-turbo）并发生成 → httpx 异步下载到本地 `data/images/` → 通过 `/images` 静态目录访问（永久有效）
- **风格**：插画卡通 / 写实摄影 / 科技未来 / 简约扁平 / 国潮古风
- **单张重生成**：operation=regenerate + scene 参数（保持场景一致换一张）
- **代码规范**：async 异步（httpx / asyncio.to_thread）、统一 logger、自定义 BizException + 全局异常处理器、配置全部走 .env

---

## 商业价值

### 用户价值

- **10 倍效率提升**：3 分钟输出初稿 + 自动配图 + 自动排版
- **爆文率提升 300%**：通过爆文逻辑分析，提炼平台推荐机制
- **降低 80% 人力成本**：月付 199 元替代人工文案编辑（月薪 8000-15000 元）
- **零配图烦恼**：AI 自动配图，语义匹配，零版权风险
- **多平台一键适配**：一键切换平台风格，自动适配格式要求

### 市场规模

- **目标用户群体**：4500 万自媒体创作者
- **付费转化率**：5%（解决真实痛点）
- **保守营收测算**：年营收 8100 万元（0.1% 市场份额）
- **乐观营收测算**：年营收 9.72 亿元（1% 市场份额）

### 会员定价

| 会员等级 | 价格 | 核心权益 |
|---------|------|---------|
| **免费版** | 0 元 | 3 次/天生成、无配图 |
| **基础版** | 99 元/月 | 30 次/天、5 张配图/篇 |
| **专业版** | 199 元/月 | 100 次/天、10 张配图/篇、批量生成 |
| **企业版** | 999 元/月 | 无限次、无限配图、API 接口 |

---

## 开发计划

**总周期**：8-10 周（2 个月）

### 阶段划分

1. **第一阶段**（1 周）：需求分析与技术预研
2. **第二阶段**（4 周）：核心功能开发
3. **第三阶段**（2 周）：增值功能开发
4. **第四阶段**（1-2 周）：测试与优化
5. **第五阶段**（1 周）：上线准备

---

## 文档

- [完整需求分析文档](./AI爆文智能创作平台-完整需求分析文档.md)
- [API 接口文档](./docs/api.md)（开发中）
- [数据库设计文档](./docs/database.md)（开发中）
- [部署文档](./docs/deployment.md)（开发中）

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

---

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](./LICENSE) 文件。

---

## 联系方式

- 项目作者：[你的名字]
- 邮箱：[your-email@example.com]
- 项目主页：[https://github.com/yourusername/ai-viral-content-generator]

---

## 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Web 框架
- [LangGraph](https://github.com/langchain-ai/langgraph) - 智能体协作框架
- [Vue 3](https://vuejs.org/) - 渐进式前端框架
- [Element Plus](https://element-plus.org/) - Vue 3 组件库
- [通义千问](https://www.aliyun.com/product/dashscope) - 阿里云大模型
- [通义万相](https://www.aliyun.com/product/dashscope) - 阿里云图像生成

---

**⭐ 如果这个项目对你有帮助，欢迎 Star！**
