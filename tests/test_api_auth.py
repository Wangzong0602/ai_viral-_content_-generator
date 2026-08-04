"""
API 测试：用户认证与资料（auth/user 接口）

【说明】
- client 不触发 lifespan，种子数据由 fixture 提供
- Redis 会话用 fakeredis，登录/登出全流程可测
"""


class TestAuth:
    def test_register_login_logout(self, client):
        """注册 → 登录 → 登出 全流程。"""
        # 注册（自动返回 token）
        resp = client.post("/api/v1/auth/register", json={
            "phone": "19900000001", "password": "test123456", "nickname": "新用户",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        assert data["user"]["phone"] == "19900000001"
        token = data["access_token"]

        # 已注册手机号重复注册被拒
        resp = client.post("/api/v1/auth/register", json={
            "phone": "19900000001", "password": "test123456",
        })
        assert resp.status_code == 400

        # 登出 → token 失效
        resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

        # 登录（重新签发新 token）
        resp = client.post("/api/v1/auth/login", json={"account": "19900000001", "password": "test123456"})
        assert resp.status_code == 200
        assert resp.json()["user"]["nickname"] == "新用户"

    def test_login_wrong_password(self, client):
        """密码错误登录被拒。"""
        client.post("/api/v1/auth/register", json={"phone": "19911111111", "password": "test123456"})
        resp = client.post("/api/v1/auth/login", json={"account": "19911111111", "password": "wrong-password"})
        assert resp.status_code == 401

    def test_login_unknown_account(self, client):
        """未注册账号登录被拒。"""
        resp = client.post("/api/v1/auth/login", json={"account": "19999999999", "password": "test123456"})
        assert resp.status_code == 401

    def test_me_requires_auth(self, client):
        """未登录访问 /me 返回 401。"""
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_banned_user_cannot_login(self, client, db):
        """被封禁用户（status=2）不能登录。"""
        from app.models.user import User
        from app.core.security import hash_password

        user = User(phone="19922222222", password_hash=hash_password("test123456"), status=2)
        db.add(user)
        db.commit()
        resp = client.post("/api/v1/auth/login", json={"account": "19922222222", "password": "test123456"})
        assert resp.status_code == 403


class TestProfile:
    def test_update_profile(self, client):
        """修改昵称/简介。"""
        reg = client.post("/api/v1/auth/register", json={"phone": "19933333333", "password": "test123456"}).json()
        headers = {"Authorization": f"Bearer {reg['access_token']}"}

        resp = client.put("/api/v1/user/profile", json={"nickname": "新昵称", "bio": "我的简介"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["nickname"] == "新昵称"
        assert resp.json()["bio"] == "我的简介"

    def test_change_password(self, client):
        """修改密码：原密码错误被拒，正确后新密码可登录。"""
        reg = client.post("/api/v1/auth/register", json={"phone": "19944444444", "password": "test123456"}).json()
        headers = {"Authorization": f"Bearer {reg['access_token']}"}

        resp = client.put("/api/v1/user/password", json={"old_password": "wrong1", "new_password": "newpass123"}, headers=headers)
        assert resp.status_code == 400

        resp = client.put("/api/v1/user/password", json={"old_password": "test123456", "new_password": "newpass123"}, headers=headers)
        assert resp.status_code == 200

        resp = client.post("/api/v1/auth/login", json={"account": "19944444444", "password": "newpass123"})
        assert resp.status_code == 200

    def test_delete_account(self, client):
        """注销账号后无法再登录。"""
        reg = client.post("/api/v1/auth/register", json={"phone": "19955555555", "password": "test123456"}).json()
        headers = {"Authorization": f"Bearer {reg['access_token']}"}
        assert client.delete("/api/v1/user/account", headers=headers).status_code == 200
        resp = client.post("/api/v1/auth/login", json={"account": "19955555555", "password": "test123456"})
        assert resp.status_code == 403  # status=3 黑名单
