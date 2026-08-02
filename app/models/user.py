"""
用户数据模型（对应数据库 users 表）

【ORM 模型 = 数据库表的结构蓝图】
每个类属性对应表的一列，SQLAlchemy 会根据这个类自动建表 / 查询 / 插入。
字段规则来自《完整需求分析文档》7.3.1 节 users 表设计。

【类型标注 Mapped[int] 是什么？】
Mapped[类型] 是 SQLAlchemy 2.0 的新写法，声明"这一列的类型"。
配合 mapped_column(...) 配置列的具体属性（长度、索引、默认值等）。
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func  # 列类型：日期时间、字符串；func.now() 取当前时间
from sqlalchemy.orm import Mapped, mapped_column  # 2.0 风格的列声明

from app.db.session import Base  # 模型基类（来自 session.py）


class User(Base):
    """
    用户表模型。

    字段设计说明（对比文档）：
    - phone/email 用 unique=True + index=True：
      unique 保证不能注册两个相同手机号（数据库层面拦截，比代码判断更可靠）
      index 为查询建索引，手机号登录时按 phone 查会更快
    - phone/email 允许为空（nullable=True）：
      因为用户可能只用手机号注册（没有邮箱），或只用邮箱（没手机号）
    - status 用数字表示状态：1=正常 2=禁用 3=黑名单（与文档一致）
    """

    __tablename__ = "users"  # 数据库表名

    # ---------- 主键 ----------
    # primary_key=True：主键（唯一标识一条记录）
    # autoincrement=True：自增（不用手动传 id，数据库自动 +1）
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---------- 账号信息 ----------
    # 手机号：最长 20 字符，唯一，加索引，允许为空
    phone: Mapped[str | None] = mapped_column(
        String(20), unique=True, index=True, nullable=True
    )
    # 邮箱：最长 100 字符，唯一，加索引，允许为空
    email: Mapped[str | None] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    # 密码哈希：存的是 bcrypt 加密后的字符串（绝不存明文！）
    # 长度 255 足够容纳 bcrypt 的输出（约 60 字符）
    password_hash: Mapped[str] = mapped_column(String(255))

    # ---------- 个人资料 ----------
    nickname: Mapped[str] = mapped_column(String(50), default="")  # 昵称，默认空字符串
    avatar: Mapped[str] = mapped_column(String(255), default="")  # 头像 URL 地址
    bio: Mapped[str] = mapped_column(String(500), default="")  # 个人简介

    # ---------- 账号状态 ----------
    # comment= 参数会把说明写进数据库表注释，方便看表结构
    # 1:正常 2:禁用 3:黑名单（注销）
    status: Mapped[int] = mapped_column(default=1, comment="1:正常 2:禁用 3:黑名单")
    # 是否管理员（后台管理系统权限）：1=管理员 0=普通用户
    is_admin: Mapped[int] = mapped_column(default=0, comment="1:管理员 0:普通用户")

    # ---------- 时间戳 ----------
    # server_default=func.now()：由数据库在插入时自动填当前时间
    #   （比 Python 端填更可靠，不依赖代码）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # onupdate=func.now()：每次 UPDATE 更新时，数据库自动刷新该时间
    #   所以修改资料后 updated_at 会自动变成最新时间，无需手动赋值
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
