"""
API 测试：配额拦截 + 管理端（套餐/订单/权限/续期）
"""

from datetime import datetime

from app.services.membership_service import activate_membership
from app.services import quota_service


class TestQuotaApi:
    def test_quota_report(self, client, user_token):
        """今日用量接口返回 4 个动作。"""
        token, _ = user_token
        resp = client.get("/api/v1/membership/quota", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"article", "analyze", "image", "batch"}
        assert data["article"]["limit"] == 3  # 免费版

    def test_free_analyze_limited(self, client, user_token, monkeypatch):
        """免费用户第 4 次逆向分析被拒（mock AI，避免真实调用）。"""
        token, _ = user_token
        headers = {"Authorization": f"Bearer {token}"}
        monkeypatch.setattr("app.api.v1.content.analyze_service", _FakeAnalyzeService())

        for _ in range(3):
            resp = client.post("/api/v1/content/analyze", json={"input_text": "测试文章内容" * 20}, headers=headers)
            assert resp.status_code == 200

        resp = client.post("/api/v1/content/analyze", json={"input_text": "测试文章内容" * 20}, headers=headers)
        assert resp.status_code == 403
        assert "次数已用完" in resp.json()["detail"]

    def test_free_batch_blocked(self, client, user_token):
        """免费用户批量生成被拒（batch_limit=0）。"""
        token, _ = user_token
        resp = client.post(
            "/api/v1/content/batch",
            json={"name": "批量", "platform": "小红书", "keywords_text": "AI\n健康"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "需要开通会员" in resp.json()["detail"]

    def test_pro_batch_allowed(self, client, seed_plans, user_token, db, monkeypatch):
        """专业用户批量生成放行（且按篇数扣文章配额）。"""
        token, user = user_token
        activate_membership(db, user.id, seed_plans["pro"].id, "专业版", datetime.now())
        db.commit()  # 显式提交（activate_membership 内部只 add 不 commit）

        class FakeGroup:
            def __init__(self, tasks):
                self.tasks = tasks

            def apply_async(self):
                return None

        monkeypatch.setattr("celery.group", FakeGroup)
        resp = client.post(
            "/api/v1/content/batch",
            json={"name": "批量", "platform": "小红书", "keywords_text": "AI\n健康\n职场"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 3
        # 文章配额被扣 3 次
        usage = quota_service.get_daily_usage(db, user)
        assert usage["article"]["used"] == 3


class _FakeAnalyzeService:
    """假的逆向分析服务：不走 AI，返回固定报告。"""

    async def analyze_viral_article(self, input_text: str) -> dict:
        return {
            "title": "测试文章",
            "content_len": len(input_text),
            "report": {
                "title_hook": "数字+悬念",
                "opening_3s": "痛点共鸣",
                "content_structure": "痛点→方案→行动",
                "emotion_points": "好奇、焦虑",
                "cta": "收藏关注",
                "seo_keywords": "测试、效率",
                "overall": "整体方法论",
            },
        }


class TestAdminApi:
    def test_non_admin_forbidden(self, client, user_token):
        """普通用户访问后台接口 → 403。"""
        token, _ = user_token
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/v1/admin/stats", headers=headers).status_code == 403
        assert client.get("/api/v1/admin/users", headers=headers).status_code == 403
        assert client.get("/api/v1/admin/plans", headers=headers).status_code == 403

    def test_admin_stats(self, client, admin_token, seed_plans, user_token):
        """管理员统计：含订单/金额字段。"""
        token, _ = admin_token
        stats = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"}).json()
        assert "total_users" in stats
        assert "paid_amount_yuan" in stats

    def test_admin_plan_crud(self, client, admin_token, seed_plans, user_token):
        """套餐增删改：新增 → 编辑 → 下架。"""
        token, _ = admin_token
        headers = {"Authorization": f"Bearer {token}"}

        # 新增
        resp = client.post("/api/v1/admin/plans", json={
            "code": "test", "name": "测试版", "price_yuan": 49.5, "duration_days": 30,
            "features": {"daily_articles": 10}, "description": "测试", "sort_order": 9, "status": 1,
        }, headers=headers)
        assert resp.status_code == 200
        plan_id = resp.json()["id"]
        assert resp.json()["price_yuan"] == 49.5

        # 重复 code 被拒
        resp = client.post("/api/v1/admin/plans", json={
            "code": "test", "name": "重复", "price_yuan": 1, "duration_days": 30,
        }, headers=headers)
        assert resp.status_code == 400

        # 编辑
        resp = client.put(f"/api/v1/admin/plans/{plan_id}", json={"name": "改名版", "price_yuan": 59}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "改名版"
        assert resp.json()["price_yuan"] == 59.0

        # 下架后 C 端不可见
        client.delete(f"/api/v1/admin/plans/{plan_id}", headers=headers)
        user_headers = {"Authorization": f"Bearer {user_token[0]}"}
        codes = [p["code"] for p in client.get("/api/v1/membership/plans", headers=user_headers).json()]
        assert "test" not in codes

    def test_admin_grant_membership(self, client, admin_token, seed_plans, user_token):
        """管理员手动续期：用户立即获得会员。"""
        admin_headers = {"Authorization": f"Bearer {admin_token[0]}"}
        user_headers = {"Authorization": f"Bearer {user_token[0]}"}
        _, user = user_token

        resp = client.put(
            f"/api/v1/admin/users/{user.id}/membership",
            json={"plan_id": seed_plans["pro"].id, "days": 7},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert "已为用户" in resp.json()["message"]

        me = client.get("/api/v1/membership/me", headers=user_headers).json()
        assert me["is_active"] is True
        assert me["plan"]["code"] == "pro"

    def test_admin_grant_unknown_plan(self, client, admin_token, user_token):
        """赠予不存在的套餐被拒。"""
        headers = {"Authorization": f"Bearer {admin_token[0]}"}
        _, user = user_token
        resp = client.put(
            f"/api/v1/admin/users/{user.id}/membership",
            json={"plan_id": 9999},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_admin_orders(self, client, admin_token, seed_plans, user_token):
        """订单列表：先买一笔，管理员能查到。"""
        user_headers = {"Authorization": f"Bearer {user_token[0]}"}
        admin_headers = {"Authorization": f"Bearer {admin_token[0]}"}
        pro = seed_plans["pro"]
        order = client.post("/api/v1/membership/orders", json={"plan_id": pro.id, "channel": "virtual"}, headers=user_headers).json()
        client.post(f"/api/v1/membership/orders/{order['order_no']}/pay", headers=user_headers)

        orders = client.get("/api/v1/admin/orders", headers=admin_headers).json()
        assert len(orders) == 1
        assert orders[0]["user_nickname"] == "测试用户"
        assert orders[0]["status"] == 2
