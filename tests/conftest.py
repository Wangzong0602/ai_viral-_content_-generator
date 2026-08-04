"""
pytest 测试基座：独立测试环境（不碰真实 MySQL/Redis/AI）

【三个隔离】
1. 数据库：SQLite 内存库（StaticPool 共享同一连接）替代真实 MySQL
   —— 通过 app.dependency_overrides[get_db] 覆盖所有接口的数据库依赖
2. Redis：fakeredis（纯内存 Redis 模拟）替代真实 Redis
   —— 替换 app.services.session.redis_client 模块变量（quota/会话都走它）
3. AI 调用：不 mock 的测试绝不调用真实通义千问（花钱 + 慢）
   —— 具体接口测试里用 monkeypatch 替换 ai 相关服务函数

【为什么不用 TestClient 的 with 语法？】
with TestClient(app) 会触发 lifespan（启动钩子）→ 种子数据写入真实 MySQL！
这里直接 TestClient(app) 调用（不进入 lifespan），种子数据由 fixture 手动写入测试库。

【使用方式】
- 运行：python -m pytest tests/ -v
- 覆盖率：python -m pytest tests/ --cov=app --cov-report=term-missing
"""

import pytest
import fakeredis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # 注册所有模型（建表需要）
from app.api.deps import get_current_user
from app.db.session import Base, get_db
from app.main import app
from app.services import session as session_module
from app.services.membership_service import (
    PRO_FEATURES,
    ENTERPRISE_FEATURES,
    init_seed_plans,
)


# ---------- 测试数据库（SQLite 内存） ----------
# StaticPool + connect_args 让所有会话共享同一个内存库连接
# （SQLite 内存库默认每个连接都是独立库，必须共享才能看到彼此的数据）
TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TEST_SESSION = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


@pytest.fixture(scope="session")
def db_engine():
    """创建所有表（整个测试会话只建一次）。"""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield TEST_ENGINE
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture(autouse=True)
def clean_tables(db_engine):
    """每个测试前清空所有表（保证用例相互独立）。"""
    with TEST_ENGINE.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture
def db(db_engine):
    """测试数据库会话。"""
    s = TEST_SESSION()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """用 fakeredis 替换真实 Redis（会话存储 + 配额计数都走它）。"""
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(session_module, "redis_client", fake)
    return fake


@pytest.fixture(scope="session")
def client():
    """FastAPI 测试客户端（不触发 lifespan，避免写真实 MySQL）。"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_db(client, db_engine):
    """把接口的 get_db 依赖换成测试库会话。"""

    def _override_get_db():
        db = TEST_SESSION()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


# ---------- 种子数据 ----------

@pytest.fixture
def seed_plans(db):
    """写入专业版/企业版套餐种子（等价于生产环境的 lifespan 初始化）。"""
    init_seed_plans(db)
    # 返回套餐（code -> id 映射，方便测试引用）
    from app.models.plan import Plan
    from sqlalchemy import select

    plans = {p.code: p for p in db.scalars(select(Plan))}
    return plans


# ---------- 常用辅助 ----------

@pytest.fixture
def make_user(db):
    """创建用户（返回 User 对象）。"""
    from app.models.user import User
    from app.core.security import hash_password

    def _make(phone="19900000001", password="test123456", nickname="测试用户", is_admin=0):
        user = User(
            phone=phone,
            nickname=nickname,
            password_hash=hash_password(password),
            is_admin=is_admin,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def admin_user(make_user):
    """管理员用户。"""
    return make_user(phone="19900000001", nickname="管理员", is_admin=1)


@pytest.fixture
def user_token(client, db, make_user, fake_redis):
    """普通用户登录 token（注册+登录全流程走接口）。"""
    from app.core.security import create_access_token
    from app.services.session import session_store

    user = make_user(phone="19912345678")
    token = create_access_token(str(user.id))
    session_store.save(user.id, token)
    return token, user


@pytest.fixture
def admin_token(client, db, admin_user, fake_redis):
    """管理员登录 token。"""
    from app.core.security import create_access_token
    from app.services.session import session_store

    token = create_access_token(str(admin_user.id))
    session_store.save(admin_user.id, token)
    return token, admin_user
