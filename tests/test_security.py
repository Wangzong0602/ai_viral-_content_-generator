"""
单元测试：JWT 与密码安全（app/core/security.py）
"""

import pytest

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPassword:
    def test_hash_and_verify(self):
        """密码哈希后可以验证，且哈希不包含明文。"""
        pwd = "my-secret-123"
        hashed = hash_password(pwd)
        assert hashed != pwd  # 不能存明文
        assert verify_password(pwd, hashed)  # 正确密码能通过
        assert not verify_password("wrong-password", hashed)  # 错误密码拒绝

    def test_hash_salt(self):
        """同一密码两次哈希结果不同（bcrypt 自动加盐，防彩虹表）。"""
        assert hash_password("same") != hash_password("same")


class TestJWT:
    def test_create_and_decode(self):
        """JWT 能编码/解码，载荷里的用户 ID 一致。"""
        token = create_access_token("42")
        payload = decode_token(token)
        assert payload["sub"] == "42"

    def test_decode_invalid_token(self):
        """篡改/伪造的 token 解码必须失败。"""
        token = create_access_token("1")
        tampered = token[:-4] + "XXXX"  # 篡改签名部分
        with pytest.raises(Exception):
            decode_token(tampered)

    def test_decode_garbage(self):
        """非 token 字符串解码必须失败。"""
        with pytest.raises(Exception):
            decode_token("not-a-token")

    def test_different_users_different_tokens(self):
        """不同用户载荷生成不同 token。"""
        t1 = create_access_token("1")
        t2 = create_access_token("2")
        assert t1 != t2
