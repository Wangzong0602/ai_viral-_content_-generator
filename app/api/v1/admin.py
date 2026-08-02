"""
后台管理接口（仅管理员可访问）

【权限控制】
所有接口统一用 Depends(get_admin_user)：
- 未登录 → 401
- 已登录但非管理员 → 403
- 管理员 → 正常访问

【接口清单】
- GET    /api/v1/admin/stats         全局统计
- GET    /api/v1/admin/users         用户列表（搜索）
- PUT    /api/v1/admin/users/{id}/status   封禁/解禁
- PUT    /api/v1/admin/users/{id}/admin    设为/取消管理员
- GET    /api/v1/admin/contents      内容列表（筛选）
- DELETE /api/v1/admin/contents/{id} 删除内容（软删除）
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.admin_deps import get_admin_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import (
    AdminContentOut,
    AdminStatsOut,
    AdminUserOut,
    AdminUserStatusUpdate,
)
from app.services import admin_service
from app.schemas.user import MessageOut

router = APIRouter(prefix="/api/v1/admin", tags=["后台管理"])


@router.get("/stats", response_model=AdminStatsOut, summary="全局统计")
def global_stats(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
) -> AdminStatsOut:
    """后台首页统计总览（用户数/生成量/字数等）。"""
    return AdminStatsOut(**admin_service.get_global_stats(db))


@router.get("/users", response_model=list[AdminUserOut], summary="用户列表")
def user_list(
    keyword: str | None = Query(default=None, max_length=100, description="搜索手机号/昵称"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
) -> list[AdminUserOut]:
    """后台用户管理：查看所有用户（可搜索），附创作统计。"""
    users = admin_service.get_admin_users(db, keyword, limit)
    result = []
    for u in users:
        task_count, char_count = admin_service.get_user_stats(db, u.id)
        out = AdminUserOut.model_validate(u)
        out.task_count = task_count
        out.char_count = char_count
        result.append(out)
    return result


@router.put("/users/{user_id}/status", response_model=MessageOut, summary="封禁/解禁用户")
def user_status(
    user_id: int,
    data: AdminUserStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
):
    """
    修改用户状态（1=正常 2=禁用 3=黑名单）。

    【保护】不能操作自己（防止误把自己封了）和管理员本人。
    """
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="不能修改自己的状态")
    user = admin_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.status = data.status
    db.add(user)
    db.commit()
    return {"message": f"用户状态已更新为 {data.status}"}


@router.put("/users/{user_id}/admin", response_model=MessageOut, summary="设置/取消管理员")
def user_admin(
    user_id: int,
    is_admin: bool = Query(default=True, description="true=设为管理员 false=取消"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
):
    """设置或取消某个用户的管理员权限。"""
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="不能修改自己的管理员权限")
    user = admin_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_admin = 1 if is_admin else 0
    db.add(user)
    db.commit()
    return {"message": "已设为管理员" if is_admin else "已取消管理员"}


@router.get("/contents", response_model=list[AdminContentOut], summary="内容列表")
def content_list(
    keyword: str | None = Query(default=None, max_length=100, description="搜索标题/主题"),
    platform: str | None = Query(default=None, description="平台筛选"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
) -> list[AdminContentOut]:
    """后台内容管理：查看所有用户的生成记录。"""
    contents = admin_service.get_admin_contents(db, keyword, platform, limit)
    result = []
    for c in contents:
        out = AdminContentOut.model_validate(c)
        out.content_length = len(c.content or "")
        # 关联用户昵称
        user = db.get(User, c.user_id)
        out.user_nickname = user.nickname if user else ""
        result.append(out)
    return result


@router.delete("/contents/{content_id}", response_model=MessageOut, summary="删除内容")
def content_delete(
    content_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
):
    """删除一条生成记录（软删除 status=3）。"""
    content = admin_service.get_content_by_id(db, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="内容不存在")
    content.status = 3
    db.add(content)
    db.commit()
    return {"message": "内容已删除"}
