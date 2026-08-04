"""
单元测试：批量关键词解析（app/services/batch_service.py）
"""

import pytest

from app.core.exceptions import BizException
from app.services import batch_service


class TestParseKeywords:
    def test_newline_separated(self):
        """每行一个关键词。"""
        assert batch_service.parse_keywords("AI 工具\n健康养生\n职场成长") == ["AI 工具", "健康养生", "职场成长"]

    def test_comma_and_chinese_separators(self):
        """逗号/分号/顿号分隔。"""
        assert batch_service.parse_keywords("AI,健康；职场、效率") == ["AI", "健康", "职场", "效率"]

    def test_dedup_and_strip(self):
        """去重 + 去首尾空格。"""
        assert batch_service.parse_keywords("  AI  \nAI\n 健康 ") == ["AI", "健康"]

    def test_empty_input(self):
        """空输入返回空列表。"""
        assert batch_service.parse_keywords("") == []
        assert batch_service.parse_keywords(",,,;;") == []

    def test_cap_at_max(self):
        """超过单次上限的输入被截断（防滥用烧钱）。"""
        raw = "\n".join(f"关键词{i}" for i in range(200))
        keywords = batch_service.parse_keywords(raw)
        assert len(keywords) <= batch_service.MAX_BATCH_ITEMS


class TestCreateBatch:
    def test_empty_keywords_rejected(self, db):
        """空关键词列表创建批量任务被拒。"""
        with pytest.raises(BizException, match="没有可用的关键词"):
            batch_service.create_batch(db, user_id=1, name="t", platform="小红书", keywords=[])

    def test_too_many_rejected(self, db):
        """超过单次上限被拒。"""
        keywords = [f"关键词{i}" for i in range(batch_service.MAX_BATCH_ITEMS + 1)]
        with pytest.raises(BizException, match="单次最多生成"):
            batch_service.create_batch(db, user_id=1, name="t", platform="小红书", keywords=keywords)

    def test_create_batch_task(self, db, monkeypatch):
        """正常创建：任务落库 + 投递 Celery（mock 掉投递）。"""
        # mock 掉 Celery group（防止真实投递到队列）
        class FakeGroup:
            def __init__(self, tasks):
                self.tasks = tasks

            def apply_async(self):
                return None

        monkeypatch.setattr("celery.group", FakeGroup)
        batch = batch_service.create_batch(db, user_id=1, name="测试批量", platform="小红书", keywords=["AI", "健康"])
        assert batch.user_id == 1
        assert batch.name == "测试批量"
        assert batch.status == 1  # 生成中（已投递）
        from app.models.batch_task import BatchItem
        from sqlalchemy import select

        items = list(db.scalars(select(BatchItem).where(BatchItem.batch_id == batch.id)))
        assert len(items) == 2
