"""
数据库会话模块：负责和 MySQL 建立连接、管理会话

【先理解概念】
- 引擎（Engine）：SQLAlchemy 的核心，管理"数据库连接池"。
  连接池 = 预先建立好的一批连接，用的时候取一条、用完还回去，
  避免每次操作都重新建立连接（建立连接很慢）。
- 会话（Session）：一次"数据库交互工作单元"。
  你可以理解为"一个临时工作区"：往里塞数据、查询数据，最后统一提交。
  - commit()：把工作区里的改动真正写进数据库（事务提交）
  - rollback()：放弃改动（事务回滚）
  - 请求处理完必须 close()，把连接还给连接池

【FastAPI 依赖注入流程】
每个接口函数里写 `db: Session = Depends(get_db)` 时：
1. FastAPI 调用 get_db()，创建/获取一个会话
2. 接口函数执行期间使用这个会话
3. 请求结束，finally 里调用 db.close() 关闭会话
这样每个请求都用独立的会话，互不干扰，也不会泄漏连接。
"""

from typing import Generator

from sqlalchemy import create_engine  # 创建数据库引擎
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker  # ORM 相关

from app.core.config import settings

# ---------- 创建数据库引擎 ----------
engine = create_engine(
    settings.DATABASE_URL,  # 从配置文件读取连接串（含账号密码、库名）
    # pool_pre_ping=True：每次取连接前先"ping"一下，
    #   如果连接已断开（比如 MySQL 重启过），自动换一条新连接，
    #   避免"connection is closed"之类的报错
    pool_pre_ping=True,
    # pool_recycle=3600：连接最长使用 1 小时就回收重建。
    #   因为 MySQL 默认 8 小时断开空闲连接，
    #   提前回收可以防止用到"已过期"的连接
    pool_recycle=3600,
    # echo=True：把执行的 SQL 打印到控制台，方便调试。
    #   生产环境应设为 False（配置里的 DEBUG 控制）
    echo=settings.DEBUG,
)

# ---------- 创建会话工厂 ----------
# sessionmaker 是一个"会话生成器"：调用 SessionLocal() 就能得到一个会话
# - bind=engine：会话绑定到上面的引擎（连接池）
# - autoflush=False：不在"查询前"自动把改动刷进数据库（避免意外行为，由我们手动控制）
# - autocommit=False：不自动提交，必须手动 commit()（这是标准做法，保证事务安全）
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """
    ORM 模型基类。

    【ORM 是什么？】
    ORM = 对象关系映射。简单说：让我们用"Python 类"来操作数据库表，
    而不需要写 SQL。比如：
    - 定义一个类 User(Base)，就等于定义了一张叫 users 的表
    - user = User(phone="138...") 就是一条记录
    - db.add(user) + db.commit() 就是 INSERT 插入

    所有数据模型（如 User）都要继承这个 Base，
    这样 Base.metadata 才能收集到所有表定义，用于建表（见 app/init_db.py）。
    """

    pass


def get_db() -> Generator[Session, None, None]:
    """
    获取一个数据库会话（FastAPI 依赖）。

    【为什么用 yield 而不是 return？】
    这是 Python 生成器的用法，配合 FastAPI 的依赖注入：
    1. 接口调用时执行到 yield，把会话 db 传给接口函数
    2. 接口函数执行完毕，代码回到 finally 块
    3. finally 保证无论接口成功还是报错，会话都一定会被关闭
    这就是"用完必须归还"的规范写法，防止数据库连接泄漏。
    """
    db = SessionLocal()  # 从连接池取一个会话
    try:
        yield db  # 把会话交给接口函数使用
    finally:
        db.close()  # 接口处理完，关闭会话（归还连接）
