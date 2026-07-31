"""
用户业务逻辑模块（核心逻辑都在这）

【为什么要单独建一个 service 层？】
把"业务规则"和"接口路由"分开：
- api 层（auth.py / user.py）：只负责接收请求、调用业务、返回结果（很薄）
- service 层（本文件）：负责真正的业务规则（查重、校验密码、改资料……）

好处：
1. 逻辑清晰：接口文件就几行，业务规则集中在这里看
2. 可复用：以后后台管理、API 接口等也要"查用户/改用户"，直接复用这里的方法
3. 可测试：业务逻辑和 HTTP 解耦，可以直接写单元测试

【HTTPException 是什么？】
抛出去后 FastAPI 会把它转成 HTTP 响应返回给前端：
- HTTPException(status_code=400, detail="该手机号已注册")
  → 前端收到 {"detail": "该手机号已注册"}，状态码 400
status 模块提供了语义化常量：400=参数错误 401=未认证 403=无权限 404=不存在
"""

from fastapi import HTTPException, status  # status: HTTP 状态码常量
from sqlalchemy import or_, select  # or_：OR 条件；select：构造查询
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.user import PasswordChange, UserLogin, UserRegister, UserUpdate


class UserService:
    """
    用户服务类：封装用户相关的所有业务逻辑。
    全部用 @staticmethod（静态方法）：不依赖实例状态，直接 UserService.register(...) 调用。
    """

    @staticmethod
    def register(db: Session, data: UserRegister) -> User:
        """
        注册新用户。

        【逻辑步骤】
        1. 去掉手机号首尾空格（用户可能输入 " 138..."）
        2. 查数据库：这个手机号是否已存在？
        3. 已存在 → 抛 400 错误（前端显示"该手机号已注册"）
        4. 不存在 → 创建 User 对象：
           - 密码必须先 hash_password 再存（绝不存明文！）
           - 昵称没填就自动生成："用户" + 手机号后 4 位
        5. db.add(user)：把对象放入会话（内存中，还没写库）
        6. db.commit()：真正写入数据库（INSERT）
        7. db.refresh(user)：重新从数据库读取该行（拿到数据库自动生成的时间戳等）

        【为什么查重要用数据库查而不是 Python 判断？】
        虽然 phone 字段有 unique 约束（数据库层面兜底），
        但这里提前查一次是为了给出友好的错误提示，而不是数据库抛 500 错误。
        """
        account = data.phone.strip()  # 清理手机号首尾空格
        existing = db.scalar(select(User).where(User.phone == account))
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,  # 400：客户端参数问题
                detail="该手机号已注册",
            )
        user = User(
            phone=account,
            nickname=data.nickname or f"用户{account[-4:]}",  # 没填昵称就用默认
            password_hash=hash_password(data.password),  # 密码加密后存储
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def login(db: Session, data: UserLogin) -> User:
        """
        用户登录。

        【逻辑步骤】
        1. 用账号（手机号或邮箱）查用户：
           or_(User.phone == account, User.email == account)
           = "phone 等于 account 或者 email 等于 account"
        2. 校验密码：
           - 用户不存在 → 直接走"账号或密码错误"分支（不暴露用户是否存在）
           - 密码不匹配 → 同样返回"账号或密码错误"
           【为什么要合并错误提示？】
           防止攻击者用登录接口"探测"哪些手机号注册过。
           如果提示"账号不存在"，攻击者就能批量试出注册用户；统一提示则无从探测。
        3. 检查账号状态：被禁用（status != 1）则拒绝登录

        :return: 登录成功的 User 对象（调用方负责生成 token）
        """
        account = data.account.strip()
        user = db.scalar(
            select(User).where(
                or_(User.phone == account, User.email == account)
            )
        )
        # 注意：两个失败条件合并判断，统一报错（安全考虑，见上方注释）
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,  # 401：认证失败
                detail="账号或密码错误",
            )
        if user.status != 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,  # 403：认证通过但无权限
                detail="账号已被禁用",
            )
        return user

    @staticmethod
    def update_profile(db: Session, user: User, data: UserUpdate) -> User:
        """
        修改个人资料。

        【核心技巧：exclude_unset=True 是什么？】
        model_dump() 把 UserUpdate 对象转成字典。
        exclude_unset=True 表示：只保留"前端真的传了"的字段。
        - 前端只传 {"nickname": "新名字"} → 字典只有 {"nickname": "新名字"}
        - 不会包含 avatar/bio（默认值是 None，但"没传"和"传了 null"是有区别的）
        然后循环给 user 对象对应属性赋值。
        这样就能做到"只更新传了的字段，没传的保持原样"。

        为什么不用 db.query + 手动逐个判断？因为通用写法更简洁，
        以后加新字段（比如头像）只要在 UserUpdate 里加字段即可，这里不用改。
        """
        payload = data.model_dump(exclude_unset=True)
        for field, value in payload.items():
            # setattr(对象, 属性名, 值)：动态给对象赋值，等价于 user.nickname = value
            setattr(user, field, value)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def change_password(db: Session, user: User, data: PasswordChange) -> None:
        """
        修改密码。

        【逻辑】
        1. 先用"原密码"验证身份：verify_password(输入的原密码, 库里存的哈希)
        2. 原密码不对 → 400 错误（不会告诉你新密码格式问题，先验身份）
        3. 原密码正确 → 把新密码哈希后覆盖存储
        4. commit 提交

        【为什么修改密码后 token 不失效？】
        严谨的做法是让旧 token 全部失效（清空该用户所有会话），
        但需要维护"用户 -> 会话"的映射关系，当前实现里没有。
        目前靠 Redis 会话 + 前端引导"请重新登录"兜底，够用即可，
        后续可以在 Redis 里加"密码版本号"来彻底解决。
        """
        if not verify_password(data.old_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="原密码错误",
            )
        user.password_hash = hash_password(data.new_password)
        db.add(user)
        db.commit()

    @staticmethod
    def build_token(user: User) -> str:
        """
        为用户生成 JWT 令牌。

        把用户 ID 转成字符串作为令牌的 subject（JWT 标准字段"主题"），
        后续每次请求都靠它认出"这是哪个用户"（见 app/api/deps.py）。
        """
        return create_access_token(subject=str(user.id))
