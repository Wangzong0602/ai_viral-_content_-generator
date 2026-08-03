"""
测试数据安全清理脚本

【重要安全说明】
本脚本【只】删除测试专用数据：
- 手机号以 199 开头的用户（测试号段，且非管理员）
- 这些用户名下的：创作记录、配图记录、批量任务、订单、会员记录

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

# 与用户关联、需要级联清理的表（全部按"199 号段且非管理员用户"过滤）
# 注意：batch_items 靠 batch_id 关联 batch_tasks，需单独处理，不在这里
USER_LINKED_TABLES = ["creation_tasks", "image_records", "batch_tasks", "orders", "memberships"]


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

            table_counts: dict[str, int] = {}
            for table in USER_LINKED_TABLES:
                cur.execute(
                    f"""SELECT COUNT(*) FROM {table}
                        WHERE user_id IN (
                            SELECT id FROM users WHERE phone LIKE %s AND is_admin != 1
                        )""",
                    (f"{TEST_PHONE_PREFIX}%",),
                )
                table_counts[table] = cur.fetchone()[0]
            # batch_items 无 user_id 列，通过 batch_tasks 的 id 关联
            cur.execute(
                """SELECT COUNT(*) FROM batch_items
                   WHERE batch_id IN (
                       SELECT id FROM batch_tasks WHERE user_id IN (
                           SELECT id FROM users WHERE phone LIKE %s AND is_admin != 1
                       )
                   )""",
                (f"{TEST_PHONE_PREFIX}%",),
            )
            table_counts["batch_items"] = cur.fetchone()[0]

            total = sum(table_counts.values())
            print(f"将删除测试数据：{user_count} 个用户、{total} 条关联记录")
            for table, count in table_counts.items():
                print(f"  - {table}: {count} 条")
            print(f"（仅限手机号 {TEST_PHONE_PREFIX} 开头且非管理员，真实账号不受影响）")
            confirm = input("确认删除？输入 y 继续，其他任意键取消: ").strip().lower()
            if confirm != "y":
                print("已取消，未删除任何数据")
                return

            # 先删 batch_items（靠 batch_id 关联），再删其他关联表，最后删用户（均排除管理员）
            cur.execute(
                """DELETE FROM batch_items
                   WHERE batch_id IN (
                       SELECT id FROM batch_tasks WHERE user_id IN (
                           SELECT id FROM users WHERE phone LIKE %s AND is_admin != 1
                       )
                   )""",
                (f"{TEST_PHONE_PREFIX}%",),
            )
            deleted_items = cur.rowcount
            for table in USER_LINKED_TABLES:
                cur.execute(
                    f"""DELETE FROM {table}
                        WHERE user_id IN (
                            SELECT id FROM users WHERE phone LIKE %s AND is_admin != 1
                        )""",
                    (f"{TEST_PHONE_PREFIX}%",),
                )
            cur.execute(
                "DELETE FROM users WHERE phone LIKE %s AND is_admin != 1",
                (f"{TEST_PHONE_PREFIX}%",),
            )
            deleted_users = cur.rowcount
            conn.commit()

            print(f"完成：删除 {deleted_users} 个测试用户、{deleted_items} 条批量子项")
            for table in USER_LINKED_TABLES:
                print(f"  - {table}: {table_counts[table]} 条")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
