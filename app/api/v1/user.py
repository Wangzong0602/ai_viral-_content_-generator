"""
用户资料接口：修改资料 / 修改密码 / 注销账号

【与 auth.py 的分工】
- auth.py：负责"认证"（你是谁）——注册、登录、登出、查当前用户
- user.py：负责"资料管理"（改你的信息）——改昵称、改密码、注销

【共同点】
这三个接口都需要登录，所以都写了 current_user: User = Depends(get_current_user)，
FastAPI 会先做身份认证（deps.py），认证通过才进入函数体。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import MessageOut, PasswordChange, UserOut, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/api/v1/user", tags=["用户"])


@router.put("/profile", response_model=UserOut, summary="修改个人信息")
def update_profile(
    data: UserUpdate,  # 前端传来的新资料（昵称/头像/简介，可部分提交）
    db: Session = Depends(get_db),  # 数据库会话
    current_user: User = Depends(get_current_user),  # 当前登录用户
):
    """
    修改个人资料接口。

    【逻辑】
    1. 先认证：current_user 就是"正在操作的用户"
    2. UserService.update_profile：
       - 只更新"前端传了的字段"（exclude_unset 技巧，见 user_service.py）
       - 没传的字段保持原样
    3. 返回更新后的完整用户信息（前端可直接刷新页面数据）
    """
    user = UserService.update_profile(db, current_user, data)
    return UserOut.from_user(user)


@router.put("/password", response_model=MessageOut, summary="修改密码")
def change_password(
    data: PasswordChange,  # 原密码 + 新密码
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    修改密码接口。

    【流程】
    1. 认证身份（必须登录才能改自己的密码）
    2. UserService.change_password 内部：
       - 先校验"原密码"是否正确（防止别人拿到你登录态后乱改）
       - 正确 → 新密码哈希后覆盖存储
    3. 返回提示"请重新登录"：
       【为什么建议重新登录？】
       密码已变，旧 token 在 7 天内的会话依然有效（当前实现不强制踢下线），
       提示重新登录是最稳妥的收尾方式。
    """
    UserService.change_password(db, current_user, data)
    return {"message": "密码修改成功，请重新登录"}


@router.delete("/account", response_model=MessageOut, summary="注销账号")
def delete_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    注销账号接口。

    【为什么"注销"只是改 status=3 而不是删记录？】
    软删除 vs 硬删除：
    - 硬删除：DELETE 从数据库删掉记录 → 数据没了，无法恢复，关联数据也断裂
    - 软删除：把 status 改为 3（黑名单）→ 记录还在，但：
      a. 无法再登录（login 里 status != 1 拒绝，deps.py 第4层也拦截）
      b. 保留历史数据（生成记录等关联表不至于悬空）
      c. 以后想恢复账号，改回 1 即可
    所以业务上"禁用/注销"普遍用软删除。
    """
    current_user.status = 3  # 标记为黑名单（注销）
    db.add(current_user)
    db.commit()
    return {"message": "账号已注销"}
