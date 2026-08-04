"""
单元测试：权益配额（app/services/quota_service.py）
使用 fakeredis，不依赖真实 Redis。
"""

from datetime import datetime

import pytest

from app.core.exceptions import BizException
from app.services import quota_service
from app.services.membership_service import FREE_PLAN


class TestQuota:
    def _free_user(self, db, make_user):
        """免费用户：无会员记录，走 FREE_PLAN 权益。"""
        return make_user()

    def test_free_plan_limits(self, db, make_user):
        """免费版权益：文章 3 次/天、配图与批量禁用。"""
        user = self._free_user(db, make_user)
        features = quota_service.get_user_plan_features(db, user)
        assert features["daily_articles"] == 3
        assert features["image_per_article"] == 0
        assert features["batch_limit"] == 0

    def test_consume_article_decrements(self, db, make_user, fake_redis):
        """消耗文章配额后剩余次数减少。"""
        user = self._free_user(db, make_user)
        remaining = quota_service.consume_quota(db, user, "article", 1)
        assert remaining == 2
        remaining = quota_service.consume_quota(db, user, "article", 1)
        assert remaining == 1

    def test_article_limit_reached(self, db, make_user, fake_redis):
        """免费用户第 4 次生成被拒（每天 3 次）。"""
        user = self._free_user(db, make_user)
        for _ in range(3):
            quota_service.consume_quota(db, user, "article", 1)
        with pytest.raises(BizException, match="次数已用完"):
            quota_service.consume_quota(db, user, "article", 1)
        # 超限时计数回滚：仍为 3（不白扣）
        usage = quota_service.get_daily_usage(db, user)
        assert usage["article"]["used"] == 3

    def test_image_disabled_for_free(self, db, make_user, fake_redis):
        """免费版配图功能禁用（0 张）→ 明确拒绝并提示开通会员。"""
        user = self._free_user(db, make_user)
        with pytest.raises(BizException, match="需要开通会员"):
            quota_service.consume_quota(db, user, "image", 1)

    def test_batch_disabled_for_free(self, db, make_user, fake_redis):
        """免费版批量生成禁用。"""
        user = self._free_user(db, make_user)
        with pytest.raises(BizException, match="需要开通会员"):
            quota_service.check_quota(db, user, "batch", 5)

    def test_check_quota_does_not_consume(self, db, make_user, fake_redis):
        """check_quota 只校验不消耗。"""
        user = self._free_user(db, make_user)
        quota_service.check_quota(db, user, "article", 1)
        usage = quota_service.get_daily_usage(db, user)
        assert usage["article"]["used"] == 0

    def test_pro_unlimited_plan(self, db, seed_plans, make_user):
        """企业版权益 -1 表示不限：消耗直接放行且不计数。"""
        user = make_user()
        from app.services.membership_service import activate_membership

        activate_membership(db, user.id, seed_plans["enterprise"].id, "企业版", datetime.now())
        db.commit()  # 显式提交（activate_membership 内部只 add 不 commit）
        remaining = quota_service.consume_quota(db, user, "article", 100)
        assert remaining == -1
        usage = quota_service.get_daily_usage(db, user)
        assert usage["article"]["remaining"] == -1

    def test_daily_reset_by_date_key(self, db, make_user, fake_redis):
        """计数按日期隔离：改日期 key 后计数清零（模拟第二天）。"""
        user = self._free_user(db, make_user)
        quota_service.consume_quota(db, user, "article", 3)
        # 手动把计数 key 改为昨天的日期 → 相当于跨天
        from app.services import session

        today_key = quota_service._quota_key(user.id, "article", datetime.now().strftime("%Y%m%d"))
        session.redis_client.rename(today_key, today_key.replace(datetime.now().strftime("%Y%m%d"), "20260101"))
        usage = quota_service.get_daily_usage(db, user)
        assert usage["article"]["used"] == 0

    def test_usage_report(self, db, make_user, fake_redis):
        """用量报告结构：4 个动作都有 used/limit/remaining。"""
        user = self._free_user(db, make_user)
        usage = quota_service.get_daily_usage(db, user)
        assert set(usage.keys()) == {"article", "analyze", "image", "batch"}
        assert usage["article"]["limit"] == FREE_PLAN["features"]["daily_articles"]
