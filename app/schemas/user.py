"""
Pydantic 数据模型（请求参数校验 + 响应格式化）

【Pydantic 是干什么的？】
它是 FastAPI 的数据校验库，负责"把关"进出的数据：
- 请求进来时：自动校验格式（手机号够不够长、密码是否为空……），
  不合法直接返回 422 错误，接口函数根本不会执行
- 响应出去时：自动格式化，保证返回给前端的数据结构正确

【这里的类分两类】
1. 请求模型（Register/Login/Update/PasswordChange）：
   前端 POST/PUT 传的 JSON，FastAPI 自动解析成这些类的实例
2. 响应模型（UserOut/TokenOut/MessageOut）：
   后端返回的数据结构，保证不会把 password_hash 等敏感字段漏出去
   ——这就是为什么要有独立的 UserOut，而不是直接把 User 模型返回
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import User  # 只为类型提示（from_user 方法）


class UserBase(BaseModel):
    """
    用户基础字段（可复用的公共字段）。
    下面的 UserOut 继承它，就不用重复写 phone/email 等字段了。
    字段都可选（默认 None），因为不同场景下不一定都有值。
    """

    phone: str | None = None
    email: str | None = None
    nickname: str | None = None
    avatar: str | None = None
    bio: str | None = None


class UserRegister(BaseModel):
    """
    注册请求模型。

    Field(..., ...) 的含义：
    - 第一个参数 ...（Ellipsis）表示"必填"，不传就报错
    - min_length=6：密码至少 6 位（注意：... 和 max_length 是给密码/手机号设长度约束）
    - description：说明文字，会显示在 Swagger 文档里，方便前端开发者看
    """

    phone: str = Field(..., min_length=5, max_length=20, description="手机号")
    password: str = Field(..., min_length=6, max_length=64, description="密码")
    nickname: str | None = Field(default=None, max_length=50, description="昵称")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """
        手机号自定义校验器。

        【field_validator 是什么？】
        Pydantic 的装饰器：在解析 phone 字段时自动调用这个函数，
        函数返回的值会替换原值（可以做清洗/格式化），
        如果 raise ValueError，Pydantic 会返回 422 错误给前端。

        【这里校验什么？】
        - 手机号必须全是数字（isdigit() 判断）
        - 去掉首尾空格（strip()），防止用户多敲空格导致"同号不同串"
        """
        if not v.strip().isdigit():
            raise ValueError("手机号必须为数字")
        return v.strip()


class UserLogin(BaseModel):
    """
    登录请求模型。
    account 是"账号"字段：可以填手机号，也可以填邮箱（兼容两种登录方式）。
    """

    account: str = Field(..., description="手机号或邮箱")
    password: str = Field(..., min_length=6, max_length=64, description="密码")


class UserUpdate(BaseModel):
    """
    修改个人资料请求模型。
    所有字段都可选（可只改昵称，不传头像）。
    字段默认 None 表示"不传就是不改"，和 exclude_unset=True 配合使用
    （详见 user_service.py 的 update_profile 注释）。
    """

    nickname: str | None = Field(default=None, max_length=50)
    avatar: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=500)


class PasswordChange(BaseModel):
    """修改密码请求模型：必须同时提供原密码和新密码，校验新密码长度。"""

    old_password: str = Field(..., min_length=6, max_length=64)
    new_password: str = Field(..., min_length=6, max_length=64)


class UserOut(UserBase):
    """
    用户信息响应模型（返回给前端的用户数据）。

    【为什么不能直接返回 User 模型对象？】
    User 模型里有 password_hash（密码哈希）！
    如果不小心返回它，用户密码哈希就泄露了（虽然不可逆，但仍是安全隐患）。
    UserOut 只包含对外安全的字段。

    ConfigDict(from_attributes=True)：
    允许直接从 ORM 对象（User 实例）转换为 UserOut。
    但我们自己写了 from_user 方法手动转换，更明确、更可控。
    """

    id: int
    status: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        """
        把 ORM 的 User 对象转换成 UserOut（只挑安全字段，手动复制）。
        这样即使以后 User 表加了敏感字段，只要 from_user 不复制，就不会泄露。
        """
        return cls(
            id=user.id,
            phone=user.phone,
            email=user.email,
            nickname=user.nickname,
            avatar=user.avatar,
            bio=user.bio,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class TokenOut(BaseModel):
    """
    登录/注册成功的响应模型。
    一次性返回：令牌 + 用户信息，前端拿到即可保存令牌并显示用户信息，
    省去再请求一次 /me 接口。
    """

    access_token: str  # JWT 令牌
    token_type: str = "bearer"  # 令牌类型（标准 OAuth 字段，固定值）
    user: UserOut  # 当前用户信息


class MessageOut(BaseModel):
    """通用消息响应模型（如"密码修改成功"这类提示）。"""

    message: str
