"""
数据库初始化脚本：自动创建所有表

【为什么需要它？】
项目里的 ORM 模型（如 User）定义了表结构，但 MySQL 里还没有对应的表。
这个脚本让 SQLAlchemy 根据模型定义自动建表，不需要手写 CREATE TABLE。

【如何运行？】
在项目根目录执行：
    python -m app.init_db

【注意事项】
create_all 只会"创建不存在的表"：
- 表不存在 → 创建
- 表已存在（哪怕结构不一致）→ 跳过，不会改动
所以这个脚本可以重复执行，是安全的。
（如果后续要改表结构，则需要用数据库迁移工具 Alembic，暂未引入）
"""

from app import models  # 导入所有模型（必须导入，否则 SQLAlchemy 不知道有哪些表）
from app.db.session import Base, engine  # 模型基类 + 数据库引擎


def init_db() -> None:
    """
    创建所有尚未存在的表。

    Base.metadata：收集了所有继承 Base 的模型类的表定义
    （因为上面 import 了 app.models，User 等模型已被加载注册）。
    create_all(bind=engine)：连接数据库，把所有表建出来。
    """
    Base.metadata.create_all(bind=engine)
    print("数据库表结构创建完成")


# 当直接运行本文件时（python -m app.init_db），执行建表逻辑
if __name__ == "__main__":
    init_db()
