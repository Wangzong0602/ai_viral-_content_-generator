"""
单元测试：SEO 优化智能体（app/agents/seo_agent.py）
"""

import json

import pytest

from app.agents import seo_agent


class TestOptimizeSeo:
    def test_normal_optimization(self, monkeypatch):
        """正常优化：返回关键词/标签/描述/标题。"""
        def fake_chat(**kwargs):
            return json.dumps(
                {
                    "content": "优化后的正文 #关键词1 #关键词2",
                    "keywords": ["关键词1", "关键词2"],
                    "hashtags": ["#关键词1", "#关键词2"],
                    "meta_description": "这是一段包含关键词1和关键词2的搜索描述。",
                    "optimized_title": "关键词1指南：优化后的标题",
                },
                ensure_ascii=False,
            )

        monkeypatch.setattr(seo_agent, "chat", fake_chat)
        result = seo_agent.optimize_seo("正文内容", "小红书", "原标题")
        assert result["content"].startswith("优化后的正文")
        assert "关键词1" in result["keywords"]
        assert result["hashtags"] == ["#关键词1", "#关键词2"]
        assert result["meta_description"]
        assert result["optimized_title"]

    def test_fallback_on_invalid_output(self, monkeypatch):
        """模型未按 JSON 返回：原样返回内容，流程不断。"""
        monkeypatch.setattr(seo_agent, "chat", lambda **kw: "不是JSON的乱输出")
        result = seo_agent.optimize_seo("原始正文", "公众号", "原标题")
        assert result["content"] == "原始正文"  # 内容不丢
        assert result["keywords"] == []
        assert result["optimized_title"] == "原标题"

    def test_fallback_on_missing_content(self, monkeypatch):
        """JSON 里没有 content 字段：同样回退。"""
        def fake_chat(**kwargs):
            return '{"keywords": ["a"]}'

        monkeypatch.setattr(seo_agent, "chat", fake_chat)
        result = seo_agent.optimize_seo("原始正文", "知乎", "标题")
        assert result["content"] == "原始正文"

    def test_platform_in_prompt(self, monkeypatch):
        """平台信息传入用户提示词（标签策略按平台）。"""
        captured = {}

        def fake_chat(**kwargs):
            captured["user_prompt"] = kwargs["user_prompt"]
            return '{"content": "正文", "keywords": [], "hashtags": [], "meta_description": "", "optimized_title": ""}'

        monkeypatch.setattr(seo_agent, "chat", fake_chat)
        seo_agent.optimize_seo("正文", "快手", "标题")
        assert "快手" in captured["user_prompt"]
