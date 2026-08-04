"""
API 测试：会员中心接口全流程（套餐/下单/支付/续期/订单）
"""


class TestPlans:
    def test_plan_list(self, client, seed_plans, user_token):
        """套餐列表：免费版 + 专业版 + 企业版，价格单位是元。"""
        token, _ = user_token
        resp = client.get("/api/v1/membership/plans", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        codes = [p["code"] for p in resp.json()]
        assert codes == ["free", "pro", "enterprise"]
        pro = next(p for p in resp.json() if p["code"] == "pro")
        assert pro["price_yuan"] == 199.0

    def test_plan_list_requires_auth(self, client):
        """未登录不能查套餐。"""
        assert client.get("/api/v1/membership/plans").status_code == 401


class TestMembershipStatus:
    def test_new_user_is_free(self, client, user_token):
        """新用户会员状态：免费版。"""
        token, _ = user_token
        resp = client.get("/api/v1/membership/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"]["code"] == "free"
        assert data["is_active"] is False
        assert data["last_end_date"] is None


class TestOrderFlow:
    def _headers(self, user_token):
        return {"Authorization": f"Bearer {user_token[0]}"}

    def test_buy_pro_plan(self, client, seed_plans, user_token):
        """下单 → 支付 → 会员开通 全流程。"""
        headers = self._headers(user_token)
        plans = client.get("/api/v1/membership/plans", headers=headers).json()
        pro = next(p for p in plans if p["code"] == "pro")

        # 下单
        resp = client.post("/api/v1/membership/orders", json={"plan_id": pro["id"], "channel": "virtual"}, headers=headers)
        assert resp.status_code == 200
        order = resp.json()
        assert order["status"] == 1  # 待支付
        assert order["amount_yuan"] == 199.0

        # 支付
        resp = client.post(f"/api/v1/membership/orders/{order['order_no']}/pay", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["already_paid"] is False

        # 会员生效
        me = client.get("/api/v1/membership/me", headers=headers).json()
        assert me["is_active"] is True
        assert me["plan"]["code"] == "pro"
        assert me["days_left"] == 29

        # 重复支付幂等
        resp = client.post(f"/api/v1/membership/orders/{order['order_no']}/pay", headers=headers)
        assert resp.json()["already_paid"] is True

        # 订单列表
        orders = client.get("/api/v1/membership/orders", headers=headers).json()
        assert len(orders) == 1
        assert orders[0]["status"] == 2

    def test_wechat_channel_blocked(self, client, seed_plans, user_token):
        """微信渠道未开通：下单被拒并提示走模拟支付。"""
        headers = self._headers(user_token)
        pro = seed_plans["pro"]
        resp = client.post("/api/v1/membership/orders", json={"plan_id": pro.id, "channel": "wechat"}, headers=headers)
        assert resp.status_code == 400
        assert "微信支付尚未开通" in resp.json()["detail"]

    def test_unknown_plan_rejected(self, client, seed_plans, user_token):
        """不存在的套餐下单被拒。"""
        headers = self._headers(user_token)
        resp = client.post("/api/v1/membership/orders", json={"plan_id": 9999, "channel": "virtual"}, headers=headers)
        assert resp.status_code == 400

    def test_cannot_pay_others_order(self, client, seed_plans, user_token, make_user):
        """不能支付别人的订单（用户隔离）。"""
        headers = self._headers(user_token)
        pro = seed_plans["pro"]
        order = client.post("/api/v1/membership/orders", json={"plan_id": pro.id, "channel": "virtual"}, headers=headers).json()

        # 另一个用户拿这个订单号去支付
        other = make_user(phone="19987654321")
        from app.core.security import create_access_token
        from app.services.session import session_store

        other_token = create_access_token(str(other.id))
        session_store.save(other.id, other_token)
        resp = client.post(
            f"/api/v1/membership/orders/{order['order_no']}/pay",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 404

    def test_cancel_order(self, client, seed_plans, user_token):
        """取消待支付订单后不能再支付。"""
        headers = self._headers(user_token)
        pro = seed_plans["pro"]
        order = client.post("/api/v1/membership/orders", json={"plan_id": pro.id, "channel": "virtual"}, headers=headers).json()
        resp = client.post(f"/api/v1/membership/orders/{order['order_no']}/cancel", headers=headers)
        assert resp.status_code == 200
        resp = client.post(f"/api/v1/membership/orders/{order['order_no']}/pay", headers=headers)
        assert resp.status_code == 400
