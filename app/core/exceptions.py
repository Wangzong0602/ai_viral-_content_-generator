"""
自定义业务异常与全局异常处理器

【为什么要自定义异常？】
1. 业务错误（如"手机号已注册""图片生成失败"）不应该让程序崩溃，
   而是返回给前端友好的提示——统一由全局处理器接管
2. 禁止裸 raise：所有可预期的业务失败都应 raise BizException，
   由全局处理器转换成规范的 JSON 响应
3. 状态码区分：
   - 4xx：客户端问题（参数错误/未认证/无权限/资源不存在）
   - 5xx：服务端问题（AI 调用失败等，前端提示稍后重试）

【全局异常处理器怎么工作？】
在 FastAPI 应用上注册 exception_handler：
- BizException → 按自定义状态码返回 {"detail": message}
- HTTPException（FastAPI 内置，如 404）→ 透传原样返回
- Exception（未知异常）→ 记录完整堆栈日志，返回 500 兜底
这样业务代码里只需要 raise，不需要 try/except 包裹每个接口。
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logger import logger


class BizException(Exception):
    """
    业务异常：业务逻辑可预期的失败统一抛这个。

    :param message: 给用户看的错误提示（会作为响应的 detail 字段）
    :param status_code: HTTP 状态码，默认 400（客户端错误）
    :param code: 业务错误码（可选，前端可据此做分支处理，默认 -1 表示无）
    """

    def __init__(self, message: str, status_code: int = 400, code: int = -1) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """在 FastAPI 应用上注册全局异常处理器（main.py 启动时调用）。"""

    @app.exception_handler(BizException)
    async def biz_exception_handler(request: Request, exc: BizException) -> JSONResponse:
        """业务异常：返回规范的错误 JSON（detail 对前端友好）。"""
        logger.warning("业务异常: %s (path=%s)", exc.message, request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """FastAPI 内置 HTTPException（如 401/404）：原样透传。"""
        logger.warning("HTTP 异常: %s %s (path=%s)", exc.status_code, exc.detail, request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        请求参数校验失败（Pydantic 自动触发的 422）。
        把校验错误整理成易读的中文提示，而不是 Pydantic 的原始结构。
        """
        logger.warning("参数校验失败: %s (path=%s)", exc.errors(), request.url.path)
        # 取第一个错误信息拼接成可读提示
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", []))
        msg = first.get("msg", "参数错误")
        return JSONResponse(
            status_code=422,
            content={"detail": f"参数校验失败: {loc} {msg}"},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        未知异常兜底：记录完整堆栈（排查关键），返回 500。
        注意：不把堆栈细节返回给前端（避免泄露内部信息），只给通用提示。
        """
        logger.exception("未捕获异常 (path=%s): %s", request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误，请稍后重试"},
        )
