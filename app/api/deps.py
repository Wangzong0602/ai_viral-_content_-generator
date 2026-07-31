"""
认证依赖模块：识别"当前请求是哪个用户"

【什么是 FastAPI 依赖（Dependency）？】
依赖就是一个"先执行、再传参"的函数。
接口里写 `current_user: User = Depends(get_current_user)` 时：
1. FastAPI 先调用 get_current_user() 完成"身份认证"
2. 认证成功 → 把 User 对象传进接口函数
3. 认证失败 → 直接返回 401/403 错误，接口函数根本不会执行

所以只要在需要登录的接口参数里加上 Depends(get_current_user)，
就自动拥有了"必须登录才能访问"的保护，一行都不用多写。

【完整的身份校验流程（4 层防线）】
┌─ 第1层：没带 token？→ 401
├─ 第2层：token 签名非法/过期？→ 401（JWT 解析失败）
├─ 第3层：token 不在 Redis 会话里？→ 401（已登出/被踢下线）
├─ 第4层：用户在数据库里？状态正常？→ 401/403
└─ 通过所有校验 → 返回 User 对象
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token  # JWT 解析
from app.db.session import get_db  # 数据库会话依赖
from app.models.user import User
from app.services.session import session_store  # Redis 会话

# HTTPBearer：从请求头解析 Bearer Token 的工具
# 前端需要在请求头带：Authorization: Bearer <token>
# auto_error=False：token 缺失时不自动报错，而是返回 None，
# 让我们自己控制错误提示（见下方第一层判断）
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    获取当前登录用户（核心认证函数，所有需要登录的接口都调用它）。

    【参数说明】
    - credentials：从请求头解析出的认证信息（含 token 字符串），
      由 bearer_scheme 依赖自动填充；没带 Authorization 头时是 None
    - db：数据库会话，由 get_db 依赖自动提供

    【每层防线的目的】
    第1层：判断"根本没带 token"
    第2层：判断"token 是假的或过期了"（JWT 库解密失败会抛异常）
    第3层：判断"token 虽然合法，但会话已被登出/删除"（Redis 双重校验）
    第4层：判断"用户是否还存在、是否被禁用"
    """
    # ---------- 第1层：没带 token ----------
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证",
        )
    token = credentials.credentials  # 取出 token 字符串

    # ---------- 第2层：token 非法或过期 ----------
    try:
        payload = decode_token(token)  # 解析 + 验签 + 查过期
        user_id = payload.get("sub")  # 取出载荷里的用户 ID
    except Exception:
        # JWT 库在"签名被篡改""已过期""格式不对"时都会抛异常
        # 统一返回 401，不向攻击者透露具体原因
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的令牌",
        )
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效令牌",
        )

    # ---------- 第3层：Redis 会话校验（token 是否已登出）----------
    stored = session_store.get(token)  # 去 Redis 查 session:<token>
    if stored is None or stored != str(user_id):
        # stored 为 None：登录时根本没存 / 已登出 / 已过期 → 会话无效
        # stored 不等于 user_id：异常情况（数据不匹配），同样拒绝
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已失效，请重新登录",
        )

    # ---------- 第4层：查数据库，确认用户存在且状态正常 ----------
    user = db.get(User, int(user_id))  # 按主键快速查询
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    if user.status != 1:
        # status != 1 表示：2=禁用 3=黑名单/已注销
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    return user  # 全部通过，把用户对象交给接口函数使用
