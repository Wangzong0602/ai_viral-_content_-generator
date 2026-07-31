"""
认证接口：注册 / 登录 / 登出 / 获取当前用户

【路由是什么？】
APIRouter 用来组织一批相关接口。
prefix="/api/v1/auth" 表示这个路由下所有接口的 URL 都以 /api/v1/auth 开头：
- POST /api/v1/auth/register → 注册
- POST /api/v1/auth/login    → 登录
- POST /api/v1/auth/logout   → 登出
- GET  /api/v1/auth/me       → 获取当前用户

【登录/注册成功的响应为什么是 TokenOut（token + 用户信息）？】
一次性返回两样东西，前端拿到后：
1. 存 token（后续请求带上）
2. 直接显示用户信息（不用再调一次 /me 接口）
减少一次网络往返，体验更好。
"""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.deps import bearer_scheme, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import TokenOut, UserLogin, UserOut, UserRegister
from app.services.session import session_store  # Redis 会话
from app.services.user_service import UserService

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post("/register", response_model=TokenOut, summary="注册")
def register(data: UserRegister, db: Session = Depends(get_db)):
    """
    注册接口。

    【流程】
    1. FastAPI 自动把请求 JSON 解析成 UserRegister（参数校验失败直接 422）
    2. UserService.register：查重 + 建用户 + 密码加密入库
    3. 生成 JWT 令牌
    4. 把令牌写入 Redis 会话（session:<token> -> 用户id），标记"已登录"
    5. 返回 {token, 用户信息}

    【为什么注册后直接发令牌？】
    用户刚注册完直接就是"已登录"状态，不用再跳回登录页输一遍密码，体验更好。

    response_model=TokenOut：声明响应结构，FastAPI 会过滤多余字段。
    """
    user = UserService.register(db, data)  # 创建用户
    token = UserService.build_token(user)  # 生成 JWT
    session_store.save(user.id, token)  # 写入 Redis 会话
    return TokenOut(access_token=token, user=UserOut.from_user(user))


@router.post("/login", response_model=TokenOut, summary="登录")
def login(data: UserLogin, db: Session = Depends(get_db)):
    """
    登录接口。

    【与注册的区别】
    不创建新用户，而是校验账号密码（UserService.login）：
    - 失败 → 抛 401"账号或密码错误"
    - 成功 → 生成新令牌 + 写入 Redis 会话
    登录一次就创建一个新会话（旧会话仍有效，即"多端登录"是允许的）。
    """
    user = UserService.login(db, data)  # 校验账号密码
    token = UserService.build_token(user)
    session_store.save(user.id, token)
    return TokenOut(access_token=token, user=UserOut.from_user(user))


@router.post("/logout", summary="登出")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    """
    登出接口。

    【逻辑】
    1. 从请求头解析出 token（没带 Authorization 头时 credentials 为 None）
    2. 从 Redis 删除 session:<token> → 这个 token 立即失效
       （下次再拿它访问 /me 等接口，deps.py 第3层校验会拒绝）
    3. 返回提示

    【为什么登出不用校验用户是否有效？】
    删除 Redis 里一个键而已，无论 token 真假都不影响安全，
    所以这里不需要 Depends(get_current_user)（登录校验）。
    """
    if credentials is not None:
        session_store.delete(credentials.credentials)  # 销毁会话
    return {"message": "已退出登录"}


@router.get("/me", response_model=UserOut, summary="获取当前用户信息")
def me(current_user: User = Depends(get_current_user)):
    """
    获取当前登录用户的信息。

    【为什么这个接口这么短？】
    因为身份识别全在 Depends(get_current_user) 里完成了（见 deps.py）：
    - 没登录 → 401，接口不执行
    - 登录了 → current_user 就是查出来的用户对象，直接返回
    """
    return UserOut.from_user(current_user)
