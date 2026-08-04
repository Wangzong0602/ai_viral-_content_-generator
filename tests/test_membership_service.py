"""
单元测试：会员业务逻辑（app/services/membership_service.py）
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.membership import Membership
from app.models.order import Order
from app.models.plan import Plan
from app.core.exceptions import BizException
from app.services import membership_service


class TestPlanList:
    def test_free_plan_always_first(self, db, seed_plans):
        """套餐列表：免费版恒在最前，付费套餐按 sort_order 排列。"""
        plans = membership_service.get_plan_list(db)
        codes = [p["code"] for p in plans]
        assert codes[0] == "free"
        assert "pro" in codes and "enterprise" in codes

    def test_off_shelf_hidden_from_c_end(self, db, seed_plans):
        """C 端列表不返回下架套餐。"""
        pro = seed_plans["pro"]
        pro.status = 2
        db.add(pro)
        db.commit()
        codes = [p["code"] for p in membership_service.get_plan_list(db)]
        assert "pro" not in codes

    def test_admin_can_see_off_shelf(self, db, seed_plans):
        """管理端列表包含下架套餐。"""
        pro = seed_plans["pro"]
        pro.status = 2
        db.add(pro)
        db.commit()
        codes = [p["code"] for p in membership_service.get_plan_list(db, include_off_shelf=True)]
        assert "pro" in codes


class TestOrderNo:
    def test_unique_and_format(self):
        """订单号：时间戳+随机字符，长度在 32 内，两次生成不同。"""
        n1 = membership_service.generate_order_no()
        n2 = membership_service.generate_order_no()
        assert n1 != n2
        assert len(n1) <= 32
        assert n1.isalnum()


class TestCreateOrder:
    def test_create_virtual_order(self, db, seed_plans, make_user):
        """虚拟渠道下单成功：待支付、金额为套餐价格快照。"""
        user = make_user()
        pro = seed_plans["pro"]
        order = membership_service.create_order(db, user, pro.id, "virtual")
        assert order.status == 1
        assert order.amount == pro.price
        assert order.plan_name == pro.name
        assert order.user_id == user.id

    def test_unknown_plan_rejected(self, db, seed_plans, make_user):
        """不存在的套餐下单被拒。"""
        user = make_user()
        with pytest.raises(BizException):
            membership_service.create_order(db, user, 99999, "virtual")

    def test_off_shelf_plan_rejected(self, db, seed_plans, make_user):
        """下架套餐不能下单。"""
        user = make_user()
        pro = seed_plans["pro"]
        pro.status = 2
        db.add(pro)
        db.commit()
        with pytest.raises(BizException):
            membership_service.create_order(db, user, pro.id, "virtual")

    def test_wechat_channel_rejected_without_config(self, db, seed_plans, make_user):
        """未开启商户资质时，微信渠道下单被拒（骨架渠道提示走模拟支付）。"""
        user = make_user()
        pro = seed_plans["pro"]
        with pytest.raises(BizException, match="微信支付尚未开通"):
            membership_service.create_order(db, user, pro.id, "wechat")

    def test_bad_channel_rejected(self, db, seed_plans, make_user):
        """非法渠道下单被拒。"""
        user = make_user()
        pro = seed_plans["pro"]
        with pytest.raises(BizException, match="不支持的支付渠道"):
            membership_service.create_order(db, user, pro.id, "bitcoin")


class TestPayAndMembership:
    def _buy(self, db, user, plan, days=None):
        """辅助：下单 + 支付，返回 (order, membership)。"""
        order = membership_service.create_order(db, user, plan.id, "virtual")
        result = membership_service.pay_order(db, order)
        return order, result

    def test_pay_activates_membership(self, db, seed_plans, make_user):
        """支付成功后自动开通会员（30 天有效期）。"""
        user = make_user()
        pro = seed_plans["pro"]
        order, result = self._buy(db, user, pro)
        assert order.status == 2  # 已支付
        assert order.paid_at is not None
        assert result["already_paid"] is False

        info = membership_service.get_user_membership(db, user.id)
        assert info["is_active"] is True
        assert info["plan"]["code"] == "pro"
        assert info["days_left"] == pro.duration_days - 1  # 30 天含今天

    def test_renew_same_plan_extends(self, db, seed_plans, make_user):
        """同套餐续费：到期日在原基础上顺延，不重置。"""
        user = make_user()
        pro = seed_plans["pro"]
        self._buy(db, user, pro)

        # 手动把到期日改成 3 天后（模拟用了 27 天）
        now = datetime.now()
        m = db.scalar(select(Membership).where(Membership.user_id == user.id))
        m.end_date = now + timedelta(days=3)
        db.add(m)
        db.commit()

        self._buy(db, user, pro)  # 续费
        info = membership_service.get_user_membership(db, user.id)
        # 3 天 + 30 天 = 33 天（含当天则显示 32）
        assert info["days_left"] == 32

    def test_switch_plan_replaces(self, db, seed_plans, make_user):
        """换套餐：旧有效会员置为取消，新套餐生效。"""
        user = make_user()
        pro = seed_plans["pro"]
        self._buy(db, user, pro)

        enterprise = seed_plans["enterprise"]
        self._buy(db, user, enterprise)

        info = membership_service.get_user_membership(db, user.id)
        assert info["plan"]["code"] == "enterprise"
        # 旧会员被取消
        old = db.scalar(
            select(Membership).where(Membership.user_id == user.id, Membership.status == 3)
        )
        assert old is not None and old.plan_id == pro.id

    def test_pay_idempotent(self, db, seed_plans, make_user):
        """同一订单重复支付不重复开通（幂等）。"""
        from sqlalchemy import func

        user = make_user()
        pro = seed_plans["pro"]
        order = membership_service.create_order(db, user, pro.id, "virtual")
        result1 = membership_service.pay_order(db, order)
        result2 = membership_service.pay_order(db, order)
        assert result1["already_paid"] is False
        assert result2["already_paid"] is True
        # 会员记录只有一条
        count = db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.user_id == user.id, Membership.status == 1)
        )
        assert count == 1

    def test_expired_membership_shows_free(self, db, seed_plans, make_user):
        """会员过期后：me 返回免费版 + last_end_date 提示。"""
        user = make_user()
        pro = seed_plans["pro"]
        self._buy(db, user, pro)

        # 手动把到期日改为昨天
        m = db.scalar(select(Membership).where(Membership.user_id == user.id))
        m.end_date = datetime.now() - timedelta(days=1)
        db.add(m)
        db.commit()

        info = membership_service.get_user_membership(db, user.id)
        assert info["is_active"] is False
        assert info["plan"]["code"] == "free"
        assert info["last_end_date"] is not None

    def test_cancel_order_only_when_pending(self, db, seed_plans, make_user):
        """只有待支付订单能取消。"""
        user = make_user()
        pro = seed_plans["pro"]
        order = membership_service.create_order(db, user, pro.id, "virtual")
        membership_service.cancel_order(db, order)
        assert order.status == 3
        # 已取消订单不能再支付
        with pytest.raises(BizException, match="订单状态不允许支付"):
            membership_service.pay_order(db, order)

    def test_activate_with_custom_days(self, db, seed_plans, make_user):
        """管理员自定义天数开通（days 覆盖套餐默认值）。"""
        user = make_user()
        pro = seed_plans["pro"]
        m = membership_service.activate_membership(
            db, user.id, pro.id, pro.name, datetime.now(), days=7
        )
        assert (m.end_date - m.start_date).days == 7
