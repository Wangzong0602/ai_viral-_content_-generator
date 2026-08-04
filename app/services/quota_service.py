"""
权益配额服务：按会员等级限制每日 AI 使用次数

【核心思想】
每个用户每天能调用多少次 AI（生成文章/逆向分析/配图/批量），
由他当前的会员套餐决定（features 里的权益字段，见 membership_service）。

【计数存在哪？为什么用 Redis 而不是 MySQL？】
- 每日次数是"临时状态"：当天清零、过期无意义，不需要长期保存
- Redis 的 INCR（自增）+ 日期 key 天然支持"每天一个计数"，且并发安全
- MySQL 存这种数据会：建表 + 每天清理，纯属浪费

【key 设计】
quota:{user_id}:{action}:{YYYYMMDD} -> 已用次数
- 带上日期：自然日自动重置（第二天 key 不同，天然清零）
- TTL 3 天：防止用户 3 天不用后 key 残留（其实隔天就无意义，3 天是兜底）

【动作与权益字段的对应】
- article（文章生成）→ daily_articles      ：生成选题时消耗 1 次
- analyze（逆向分析）→ analyze_daily       ：每次分析消耗 1 次
- image  （AI 配图）  → image_per_article   ：每张图消耗 1 次
- batch  （批量生成） → batch_limit         ：按篇消耗 article 配额 + 单次上限校验

【-1 表示不限】
企业版权益里 -1 = 不限次。此时直接放行、不计数（省 Redis 写入）。
"""

from datetime import datetime

from app.core.exceptions import BizException
from app.models.user import User
from app.services import membership_service, session

# 通过模块引用访问 Redis 客户端：
# 写成 session.redis_client 而不是 from ... import redis_client，
# 是为了测试时能 monkeypatch（from import 会把引用复制走，替换模块变量无效）
# 注意：下方函数里统一用 session.redis_client 访问

# 配额 key 前缀与过期时间（秒）
QUOTA_KEY_PREFIX = "quota:"
QUOTA_TTL_SECONDS = 3 * 24 * 3600  # 3 天兜底清理（日期 key 本身已保证次日重置）

# 动作 → 权益字段名 的映射（新增计费动作时在这里维护）
ACTION_FIELDS = {
    "article": "daily_articles",
    "analyze": "analyze_daily",
    "image": "image_per_article",
    "batch": "batch_limit",
}

# 动作的中文名（错误提示用）
ACTION_NAMES = {
    "article": "文章生成",
    "analyze": "爆文分析",
    "image": "AI 配图",
    "batch": "批量生成",
}


def get_user_plan_features(db, user: User) -> dict:
    """
    获取用户当前生效套餐的权益配置（features 字典）。

    - 会员有效 → 返回套餐 features
    - 免费/过期 → 返回内置免费版 features（FREE_PLAN）
    注意：免费用户是"无会员记录"，不是套餐记录，所以直接回退到 FREE_PLAN。
    """
    info = membership_service.get_user_membership(db, user.id)
    if info["is_active"]:
        return info["plan"].get("features") or {}
    return membership_service.FREE_PLAN["features"]


def _limit_of(features: dict, action: str) -> int:
    """取某个动作的每日上限（-1=不限，0=不可用，>0=每天 N 次）。"""
    field = ACTION_FIELDS[action]
    return int(features.get(field, 0))


def _quota_key(user_id: int, action: str, day: str) -> str:
    """拼配额 key：quota:{user_id}:{action}:{YYYYMMDD}"""
    return f"{QUOTA_KEY_PREFIX}{user_id}:{action}:{day}"


def check_quota(db, user: User, action: str, amount: int = 1) -> int:
    """
    校验配额（不消耗）：确认用户还有足够次数。

    :param db: 数据库会话（查会员套餐用）
    :param user: 当前用户
    :param action: 动作类型（article/analyze/image/batch）
    :param amount: 本次需要的次数（批量生成按篇数传）
    :return: 剩余次数（-1 表示不限）
    :raises BizException: 超出限额时抛出（带开通会员引导提示）
    """
    features = get_user_plan_features(db, user)
    limit = _limit_of(features, action)

    # 企业版：-1 = 不限，直接放行（返回 -1 表示"不限"）
    if limit == -1:
        return -1

    # 0 = 该权益未开放（免费版的配图/批量）→ 明确提示去开通会员
    if limit == 0:
        raise BizException(
            f"{ACTION_NAMES[action]}功能需要开通会员后使用，当前套餐为免费版（{ACTION_NAMES[action]}不可用）"
        )

    # 已用次数 = key 当前值（不存在视为 0）
    key = _quota_key(user.id, action, datetime.now().strftime("%Y%m%d"))
    used = int(session.redis_client.get(key) or 0)
    remaining = limit - used
    if remaining < amount:
        raise BizException(
            f"今日{ACTION_NAMES[action]}次数已用完（上限 {limit} 次），"
            f"可前往会员中心升级套餐或等待明天重置",
            status_code=403,
        )
    return remaining


def consume_quota(db, user: User, action: str, amount: int = 1) -> int:
    """
    消耗配额（先校验再计数）。

    【并发安全】用 Redis INCR 原子自增：
    先 GET 检查再 SET 会有并发竞态（两个请求同时读到剩余 1 次都放行），
    INCR 是原子操作，不会超卖。

    【计数回滚】INCR 后发现超出 → DECRBY 回滚，保证不白扣次数。
    """
    features = get_user_plan_features(db, user)
    limit = _limit_of(features, action)
    if limit == -1:
        return -1  # 不限 → 不计数

    if limit == 0:
        raise BizException(
            f"{ACTION_NAMES[action]}功能需要开通会员后使用，当前套餐为免费版（{ACTION_NAMES[action]}不可用）"
        )

    key = _quota_key(user.id, action, datetime.now().strftime("%Y%m%d"))
    used = session.redis_client.incrby(key, amount)  # 原子自增
    session.redis_client.expire(key, QUOTA_TTL_SECONDS)  # 刷新兜底过期时间

    if used > limit:
        session.redis_client.decrby(key, amount)  # 超出 → 回滚，不白扣
        raise BizException(
            f"今日{ACTION_NAMES[action]}次数已用完（上限 {limit} 次），"
            f"可前往会员中心升级套餐或等待明天重置",
            status_code=403,
        )
    return limit - used  # 返回剩余次数


def get_daily_usage(db, user: User) -> dict:
    """
    查询今日各动作已用/上限（会员中心展示用）。

    :return: {
        article: { used, limit, remaining },
        analyze: { used, limit, remaining },
        image:   { used, limit, remaining },
        batch:   { used, limit },   # 批量是"单次上限"语义，无每日计数
    }
    """
    features = get_user_plan_features(db, user)
    day = datetime.now().strftime("%Y%m%d")
    result = {}
    for action in ("article", "analyze", "image", "batch"):
        limit = _limit_of(features, action)
        if action == "batch":
            # 批量：batch_limit 是"单次最多几篇"，不是每日计数
            result[action] = {"limit": limit, "remaining": limit}
            continue
        if limit == -1:
            result[action] = {"used": 0, "limit": -1, "remaining": -1}
            continue
        used = int(session.redis_client.get(_quota_key(user.id, action, day)) or 0)
        result[action] = {"used": used, "limit": limit, "remaining": max(limit - used, 0)}
    return result
