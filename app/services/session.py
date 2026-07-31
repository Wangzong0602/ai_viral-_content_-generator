"""
Redis 会话存储模块

【为什么要用 Redis 存会话？JWT 不是已经"无状态"了吗？】

纯 JWT 方案的缺点：JWT 一旦签发，在过期前永远有效，无法主动让它失效。
这带来两个问题：
1. 用户点了"登出"，但旧 token 还能用 → 登出形同虚设
2. 用户改了密码，旧 token 依然有效 → 有安全隐患

所以我们采用"JWT + Redis 双重校验"（这是业界常见方案）：
- JWT 负责：验证令牌真伪、解析用户身份（不用查数据库）
- Redis 负责：记录"哪些 token 是有效会话"
  - 登录时：往 Redis 写一条记录 session:<token> -> 用户ID
  - 每次请求：去 Redis 查这条记录在不在，不在 = 已登出 = 拒绝访问
  - 登出时：删掉这条记录 → 这个 token 立即失效
- 过期时间：Redis 里设置 7 天 TTL，和 JWT 过期时间保持一致

【TTL 是什么？】
TTL = Time To Live（存活时间）。
Redis 的 setex 命令会设置"这条数据多少秒后自动删除"。
这样即使忘记手动清理，7 天后的旧会话也会被 Redis 自动清掉。
"""

from datetime import timedelta

import redis

from app.core.config import settings

# 创建 Redis 连接客户端
# decode_responses=True：让 Redis 返回字符串而不是字节（否则读出来是 b'1'）
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

# 会话有效期：7 天（与 JWT 的 7 天保持一致，见 config.py）
SESSION_TTL = timedelta(days=7)

# 键名前缀：所有会话 key 都以 "session:" 开头
# 好处：以后如果 Redis 里还要存别的数据（如缓存），可以用不同前缀区分，
# 也方便用 KEYS session:* 批量查询/清理
SESSION_KEY_PREFIX = "session:"


class SessionStore:
    """
    会话存储工具类（封装 Redis 的增删查操作）。

    用 staticmethod（静态方法）：
    方法不需要访问"实例自己的数据"，只是对 Redis 操作的简单封装，
    所以不需要实例化，直接 SessionStore.save(...) 调用即可。
    """

    @staticmethod
    def save(user_id: int, token: str) -> None:
        """
        登录成功后保存会话。

        setex(key, ttl, value) 的含义：
        设置一个"会自动过期"的键值对：
        - key：session:<token>（以 token 本身作为键，方便按 token 查询）
        - value：用户 ID（字符串）
        - ttl：7 天后自动删除
        """
        key = f"{SESSION_KEY_PREFIX}{token}"
        redis_client.setex(key, SESSION_TTL, str(user_id))

    @staticmethod
    def get(token: str) -> str | None:
        """
        查询某个 token 对应的会话。

        - 返回用户 ID 字符串：说明该 token 是有效会话
        - 返回 None：说明没登过、已登出、或已过期 → token 无效
        """
        return redis_client.get(f"{SESSION_KEY_PREFIX}{token}")

    @staticmethod
    def delete(token: str) -> None:
        """
        登出时删除会话，让 token 立即失效。
        （删除不存在的键 Redis 也不会报错，所以无需判断存在与否）
        """
        redis_client.delete(f"{SESSION_KEY_PREFIX}{token}")


# 创建全局唯一实例，其他模块导入使用：
# from app.services.session import session_store
session_store = SessionStore()
