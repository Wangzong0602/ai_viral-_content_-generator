"""
后台管理的数据模型（Pydantic v2 请求/响应校验）
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AdminUserOut(BaseModel):
    """后台用户列表项。"""

    id: int
    phone: str | None = None
    email: str | None = None
    nickname: str = ""
    status: int
    is_admin: int
    created_at: datetime
    # 该用户的创作统计
    task_count: int = 0
    char_count: int = 0
    # 会员信息（会员系统新增）
    plan_name: str = "免费版"  # 当前套餐名
    membership_end: datetime | None = None  # 会员到期时间（无会员为 None）

    model_config = {"from_attributes": True}


class AdminUserStatusUpdate(BaseModel):
    """修改用户状态（封禁/解禁）。"""

    status: int = Field(..., ge=1, le=3, description="1:正常 2:禁用 3:黑名单")


class AdminContentOut(BaseModel):
    """后台内容列表项。"""

    id: int
    user_id: int
    user_nickname: str = ""
    keyword: str = ""
    platform: str = ""
    selected_title: str = ""
    status: int
    quality_score: int
    content_length: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminStatsOut(BaseModel):
    """后台全局统计。"""

    total_users: int = 0  # 总用户数
    new_users_7d: int = 0  # 近 7 天新增用户
    total_contents: int = 0  # 总生成记录数
    success_contents: int = 0  # 成功生成数
    total_chars: int = 0  # 总字数
    active_users_7d: int = 0  # 近 7 天活跃用户
    # 会员/订单统计（P2 会员系统新增，默认 0 兼容旧数据）
    total_orders: int = 0  # 总订单数
    paid_orders: int = 0  # 已支付订单数
    paid_amount_yuan: float = 0  # 实收金额（元）
