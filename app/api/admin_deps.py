"""
后台管理权限依赖：仅管理员可访问的接口校验

【用法】
在后台管理接口里写：
    current_admin: User = Depends(get_admin_user)

- 先走普通登录校验（get_current_user）
- 再校验 is_admin == 1，否则返回 403
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User


def get_admin_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """
    获取当前管理员（非管理员返回 403）。

    【权限模型】
    所有后台接口统一用这个依赖，一处控制、全局生效。
    """
    if current_user.is_admin != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无管理员权限",
        )
    return current_user
