"""
API 测试：多内容形态（P3 扩展）
"""

from app.schemas.content import SUPPORTED_CONTENT_TYPES, CONTENT_TYPE_NAMES


class TestContentTypeValidation:
    def test_supported_types_defined(self):
        """四种形态齐全，且都有中文名。"""
        assert set(SUPPORTED_CONTENT_TYPES) == {"article", "video_script", "live_script", "ecommerce"}
        assert len(CONTENT_TYPE_NAMES) == 4

    def test_default_is_article(self, client, user_token):
        """不传 content_type 默认 article（兼容旧客户端）。"""
        token, _ = user_token
        # topics 接口默认形态：mock AI 后返回正常（此处只校验请求未被 422 拦截）
        from app.services import content_service

        original = content_service.get_topics
        content_service.get_topics = lambda *a, **k: {"keyword": a[0], "platform": a[1], "topics": []}
        try:
            resp = client.post(
                "/api/v1/content/topics",
                json={"keyword": "测试", "platform": "小红书"},
                headers={"Authorization": f"Bearer {token}"},
            )
            # 未被形态校验拦截（选题为空是 AI mock 的结果，不是 422）
            assert resp.status_code != 422
        finally:
            content_service.get_topics = original

    def test_unknown_type_rejected(self, client, user_token):
        """非法形态返回 422。"""
        token, _ = user_token
        resp = client.post(
            "/api/v1/content/topics",
            json={"keyword": "测试", "platform": "小红书", "content_type": "video"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
        assert "不支持的内容形态" in resp.json()["detail"]

    def test_all_types_accepted(self, client, user_token):
        """四种合法形态都通过校验（AI 用 mock）。"""
        token, _ = user_token
        from app.services import content_service

        original = content_service.get_topics
        content_service.get_topics = lambda *a, **k: {"keyword": a[0], "platform": a[1], "topics": []}
        try:
            for ct in SUPPORTED_CONTENT_TYPES:
                resp = client.post(
                    "/api/v1/content/topics",
                    json={"keyword": "测试", "platform": "小红书", "content_type": ct},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert resp.status_code != 422, f"{ct} 被校验拦截"
        finally:
            content_service.get_topics = original

    def test_content_type_passed_to_agent(self, client, user_token, monkeypatch):
        """content_type 正确传递给选题智能体。"""
        token, _ = user_token
        captured = {}

        def fake_generate_topics(keyword, platform, template_structure="", fact_context="", content_type="article"):
            captured["content_type"] = content_type
            return [{"title": "测试选题", "summary": "简介", "target_audience": "人群", "expected_effect": "效果"}]

        monkeypatch.setattr("app.agents.topic_agent.generate_topics", fake_generate_topics)
        resp = client.post(
            "/api/v1/content/topics",
            json={"keyword": "测试", "platform": "小红书", "content_type": "video_script"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert captured["content_type"] == "video_script"
        assert resp.json()["topics"][0]["title"] == "测试选题"
