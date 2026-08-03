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
- GET    /api/v1/admin/plans         会员套餐列表（含免费版）
- POST   /api/v1/admin/plans        新增套餐
- PUT    /api/v1/admin/plans/{id}   编辑套餐
- DELETE /api/v1/admin/plans/{id}   下架套餐（软删除）
- GET    /api/v1/admin/orders       订单列表（筛选）
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.admin_deps import get_admin_user
from app.core.exceptions import BizException
from app.db.session import get_db
from app.models.order import Order
from app.models.plan import Plan
from app.models.user import User
from app.schemas.admin import (
    AdminContentOut,
    AdminStatsOut,
    AdminUserOut,
    AdminUserStatusUpdate,
)
from app.schemas.membership import (
    AdminOrderOut,
    AdminPlanCreate,
    AdminPlanUpdate,
    PlanOut,
)
from app.schemas.user import MessageOut
from app.services import admin_service, membership_service

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
        # 附加会员信息：当前生效会员的套餐名 + 到期时间
        membership_info = membership_service.get_user_membership(db, u.id)
        if membership_info["is_active"]:
            out.plan_name = membership_info["plan"].get("name", "免费版")
            out.membership_end = membership_info["end_date"]
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


# ========== 会员套餐管理 ==========

@router.get("/plans", response_model=list[PlanOut], summary="套餐列表（含免费版）")
def plan_list(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
) -> list[PlanOut]:
    """
    管理端套餐列表（免费版 + 全部数据库套餐，含已下架的）。
    前端据此渲染表格，可编辑/上下架。
    """
    plans = membership_service.get_plan_list(db, include_off_shelf=True)
    return [PlanOut.from_dict(p) for p in plans]


@router.post("/plans", response_model=PlanOut, summary="新增套餐")
def plan_create(
    data: AdminPlanCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
) -> PlanOut:
    """
    新增套餐（如"季度版""终身版"）。

    【code 唯一性】
    code 是套餐标识（代码/前端判断用），重复会触发数据库唯一索引错误，
    这里先查一次给友好提示。
    """
    exists = membership_service.get_plan_by_code(db, data.code)
    if exists:
        raise BizException(f"套餐标识 {data.code} 已存在")
    plan = Plan(
        code=data.code,
        name=data.name,
        price=int(round(data.price_yuan * 100)),  # 元 → 分（防浮点误差用 round）
        duration_days=data.duration_days,
        features=data.features,
        description=data.description,
        sort_order=data.sort_order,
        status=data.status,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return PlanOut.from_dict(membership_service._plan_to_dict(plan))


@router.put("/plans/{plan_id}", response_model=PlanOut, summary="编辑套餐")
def plan_update(
    plan_id: int,
    data: AdminPlanUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
) -> PlanOut:
    """
    编辑套餐（字段可选，只更新传了的）。

    【排除规则】
    - code 不允许改（它是套餐标识，历史订单/会员记录依赖它）
    - 其余字段（名称/价格/权益/排序/上下架）均可改
    """
    plan = membership_service.get_plan_by_id(db, plan_id)
    if not plan:
        raise BizException("套餐不存在", status_code=404)

    updates = data.model_dump(exclude_unset=True)  # 只取前端传了的字段
    if "price_yuan" in updates:
        plan.price = int(round(updates.pop("price_yuan") * 100))
    for field, value in updates.items():
        setattr(plan, field, value)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return PlanOut.from_dict(membership_service._plan_to_dict(plan))


@router.delete("/plans/{plan_id}", response_model=MessageOut, summary="下架套餐")
def plan_delete(
    plan_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
):
    """
    下架套餐（软删除 status=2）。

    【为什么是"下架"而不是物理删除？】
    历史订单/会员记录里引用了套餐 ID，物理删除会导致这些记录悬空。
    下架后：C 端不可见、不可购买，历史记录依然正常显示。
    """
    plan = membership_service.get_plan_by_id(db, plan_id)
    if not plan:
        raise BizException("套餐不存在", status_code=404)
    plan.status = 2
    db.add(plan)
    db.commit()
    return {"message": f"套餐「{plan.name}」已下架"}


# ========== 订单管理 ==========

@router.get("/orders", response_model=list[AdminOrderOut], summary="订单列表")
def order_list(
    order_status: int | None = Query(default=None, ge=1, le=4, description="状态筛选：1待支付 2已支付 3已取消 4已退款"),
    keyword: str | None = Query(default=None, max_length=100, description="搜索订单号/套餐名"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
) -> list[AdminOrderOut]:
    """
    后台订单管理：全部用户的订单（可按状态/关键词筛选），附用户昵称。
    """
    orders = admin_service.get_admin_orders(db, order_status, keyword, limit)
    result = []
    for o in orders:
        user = db.get(User, o.user_id)
        result.append(AdminOrderOut.from_order(o, user.nickname if user else ""))
    return result
