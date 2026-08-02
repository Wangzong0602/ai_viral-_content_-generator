"""
应用入口：创建 FastAPI 应用、注册路由、配置接口文档

【这个文件做了什么？】
1. 创建 FastAPI 实例（应用本身）
2. 注册全局异常处理器（统一异常接管，见 core/exceptions.py）
3. 挂载静态文件目录：
   - /static：本地 Swagger UI 资源（不依赖国外 CDN）
   - /images：AI 生成的配图（本地存储）
4. 注册所有接口路由（auth、user、content、image）
5. 定义根路径 "/" 返回基础信息

【启动方式】
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
- app.main：本文件（app 包下的 main 模块）
- app：本文件里创建的 FastAPI 实例变量名
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html  # 生成 Swagger 页面 HTML
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles  # 托管静态文件

from app.api.v1 import auth, batch, content, dashboard, image, template, user  # 导入路由模块（注册路由时用到）
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logger import logger

# 静态文件目录的绝对路径（app/static）
STATIC_DIR = Path(__file__).resolve().parent / "static"
# Swagger UI 资源的 URL 前缀（浏览器访问路径）
SWAGGER_BASE = "/static/swagger"
# AI 配图的本地存储目录（由配置项解析为绝对路径）
IMAGE_STORAGE_DIR = Path(settings.IMAGE_STORAGE_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期钩子。

    【什么是生命周期？】
    服务"启动前"和"关闭后"要执行的代码放这里。
    - 启动前（yield 之前）：初始化数据库连接池、加载配置等
    - 关闭后（yield 之后）：清理资源、关闭连接等

    当前在启动时：
    - 确保图片存储目录存在（挂载静态目录前必须先创建）
    - 初始化内容模板种子数据（首次启动时写入）
    """
    IMAGE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("应用启动完成, 图片存储目录=%s", IMAGE_STORAGE_DIR)

    # 初始化内容模板种子数据（幂等：表空时才插入）
    from app.db.session import SessionLocal
    from app.services.template_service import init_seed_templates

    seed_db = SessionLocal()
    try:
        init_seed_templates(seed_db)
    finally:
        seed_db.close()

    yield
    logger.info("应用关闭")


# ---------- 创建 FastAPI 应用 ----------
app = FastAPI(
    title=settings.APP_NAME,  # 应用名（显示在 Swagger 页面上）
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    # docs_url=None：关闭 FastAPI 自带的 /docs 路由
    # （因为我们要用自定义的 /docs，加载本地 Swagger 资源）
    docs_url=None,
    redoc_url=None,  # 同样关闭 Redoc 文档（它也从外部 CDN 加载）
)

# ---------- 注册全局异常处理器 ----------
# 统一接管：BizException（业务错误）/ HTTPException（401等）/ 校验失败 / 未知异常
register_exception_handlers(app)

# ---------- 挂载静态文件目录 ----------
# 1. /static：Swagger UI 本地资源
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# 2. /images：AI 配图（本地存储，目录在 lifespan 启动时已创建）
#    html=True：允许浏览器直接访问（<img src="/images/xxx.png">）
app.mount(
    settings.IMAGE_URL_PREFIX,
    StaticFiles(directory=str(IMAGE_STORAGE_DIR), html=True),
    name="images",
)


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html() -> HTMLResponse:
    """
    自定义 Swagger UI 文档页面（http://127.0.0.1:8001/docs）。

    【为什么要自定义？】
    FastAPI 默认的 /docs 页面里，JS/CSS 是从 cdn.jsdelivr.net（国外 CDN）加载的。
    如果你的网络无法访问这个 CDN，页面就会一片空白（Swagger 根本渲染不出来）。
    解决办法：把 swagger-ui 的 js/css/favicon 下载到本地（app/static/swagger/），
    让页面从本地加载，不依赖外网。

    include_in_schema=False：这个页面本身不出现在接口文档里（它只是文档载体）。

    openapi_url：告诉页面"接口定义 JSON 在哪"（默认 /openapi.json）。
    """
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,  # 接口定义 JSON 地址
        title=f"{app.title} - Swagger UI",  # 页面标题
        swagger_js_url=f"{SWAGGER_BASE}/swagger-ui-bundle.js",  # 本地 JS
        swagger_css_url=f"{SWAGGER_BASE}/swagger-ui.css",  # 本地 CSS
        swagger_favicon_url=f"{SWAGGER_BASE}/favicon.png",  # 本地图标
    )


# ---------- 注册路由 ----------
# 把 auth.py、user.py、content.py、image.py 里的 router 挂到应用上
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(content.router)
app.include_router(image.router)
app.include_router(batch.router)
app.include_router(dashboard.router)
app.include_router(template.router)


@app.get("/")
def root():
    """根路径：用于健康检查（浏览器访问确认服务活着）。"""
    return {"message": "AI 爆文智能创作平台 API", "version": settings.APP_VERSION}
