"""
单元测试：内容模板服务 + 数据看板统计（纯 DB，不调 AI）
"""

from app.services import dashboard_service, template_service


class TestTemplateService:
    def test_seed_templates_idempotent(self, db):
        """种子模板幂等：重复初始化不会重复插入。"""
        template_service.init_seed_templates(db)
        template_service.init_seed_templates(db)
        templates = template_service.get_templates(db)
        assert len(templates) == 9  # 3 平台 × 3 结构

    def test_filter_by_platform(self, db):
        """按平台过滤模板。"""
        template_service.init_seed_templates(db)
        xhs = template_service.get_templates(db, "小红书")
        assert len(xhs) == 3
        assert all(t.platform == "小红书" for t in xhs)

    def test_get_template_by_id(self, db):
        """按 ID 查模板。"""
        template_service.init_seed_templates(db)
        templates = template_service.get_templates(db)
        t = template_service.get_template(db, templates[0].id)
        assert t is not None
        assert template_service.get_template(db, 99999) is None


class TestDashboardService:
    def test_empty_user(self, db, make_user):
        """新用户看板：全零统计（不报错）。"""
        user = make_user()
        overview = dashboard_service.get_overview(db, user.id)
        assert overview["summary"]["total_count"] == 0
        assert overview["platforms"] == []
        # 质量分布是 4 个固定区间（全 0）
        assert all(q["count"] == 0 for q in overview["quality_dist"])
        assert sum(t["count"] for t in overview["trend"]) == 0  # 30 天零数据

    def test_with_tasks(self, db, make_user):
        """有创作记录后：统计正确（按用户隔离）。"""
        from datetime import datetime

        from app.models.creation_task import CreationTask

        user = make_user()
        other = make_user(phone="19999999998")
        # 注意：去掉微秒（SQLite 的 date() 函数解析不了带微秒的时间串，会导致趋势统计失败）
        now = datetime.now().replace(microsecond=0)
        # 本用户 2 篇（1 完成 1 失败）
        # 注意：显式传 created_at（SQLite 的 func.now() 是 UTC，会导致趋势时区错位）
        db.add_all([
            CreationTask(user_id=user.id, keyword="AI", platform="小红书", selected_title="标题1", content="内容" * 50, status=2, quality_score=85, created_at=now),
            CreationTask(user_id=user.id, keyword="职场", platform="公众号", selected_title="标题2", content="", status=3, quality_score=0, error_message="超时", created_at=now),
            # 其他用户的不算
            CreationTask(user_id=other.id, keyword="别人", platform="知乎", selected_title="标题3", content="内容" * 100, status=2, quality_score=90, created_at=now),
        ])
        db.commit()

        overview = dashboard_service.get_overview(db, user.id)
        assert overview["summary"]["total_count"] == 1  # 只算已完成
        assert overview["summary"]["total_chars"] == 100
        assert overview["summary"]["failed_count"] == 1
        # 平台分布只含本用户的平台
        platform_codes = [p["platform"] for p in overview["platforms"]]
        assert set(platform_codes) == {"小红书"}
        # 质量分布：85 分落在 70-89
        q70_90 = next(q for q in overview["quality_dist"] if q["range"] == "70-89")
        assert q70_90["count"] == 1
        # 趋势 30 天共 1 篇
        assert sum(t["count"] for t in overview["trend"]) == 1
