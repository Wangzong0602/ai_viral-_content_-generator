"""
测试数据安全清理脚本

【重要安全说明】
本脚本【只】删除测试专用数据：
- 手机号以 199 开头的用户（测试号段）
- 这些用户名下的创作记录

【绝不会做】无条件全表删除（DELETE FROM users / creation_tasks）。
真实用户数据（非 199 号段）不受任何影响。

【如何运行？】python clean_test_data.py
运行前会显示将要删除的数量，输入 y 确认后才执行。
"""

import sys

import pymysql

sys.stdout.reconfigure(encoding="utf-8")

# 数据库连接信息（与 .env 保持一致）
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "010819",
    "database": "ai_content_generator",
    "charset": "utf8mb4",
}

# 测试专用号段（所有测试脚本统一使用 199 开头）
TEST_PHONE_PREFIX = "199"


def main() -> None:
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            # 统计将要删除的数据量（排除管理员账号，防止误删）
            cur.execute(
                "SELECT COUNT(*) FROM users WHERE phone LIKE %s AND is_admin != 1",
                (f"{TEST_PHONE_PREFIX}%",),
            )
            user_count = cur.fetchone()[0]
            cur.execute(
                """SELECT COUNT(*) FROM creation_tasks
                   WHERE user_id IN (
                       SELECT id FROM users WHERE phone LIKE %s AND is_admin != 1
                   )""",
                (f"{TEST_PHONE_PREFIX}%",),
            )
            task_count = cur.fetchone()[0]

            print(f"将删除测试数据：{user_count} 个用户、{task_count} 条创作记录")
            print(f"（仅限手机号 {TEST_PHONE_PREFIX} 开头且非管理员，真实账号不受影响）")
            confirm = input("确认删除？输入 y 继续，其他任意键取消: ").strip().lower()
            if confirm != "y":
                print("已取消，未删除任何数据")
                return

            # 先删创作记录（外键依赖），再删用户（均排除管理员）
            cur.execute(
                """DELETE FROM creation_tasks
                   WHERE user_id IN (
                       SELECT id FROM users WHERE phone LIKE %s AND is_admin != 1
                   )""",
                (f"{TEST_PHONE_PREFIX}%",),
            )
            deleted_tasks = cur.rowcount
            cur.execute(
                "DELETE FROM users WHERE phone LIKE %s AND is_admin != 1",
                (f"{TEST_PHONE_PREFIX}%",),
            )
            deleted_users = cur.rowcount
            conn.commit()

            print(f"完成：删除 {deleted_users} 个测试用户、{deleted_tasks} 条创作记录")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
