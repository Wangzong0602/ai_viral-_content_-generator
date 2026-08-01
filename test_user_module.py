"""
用户模块全流程自动化测试脚本

【这个脚本是干什么的？】
模拟一个真实用户从头到尾操作一遍：
注册 → 查信息 → 改资料 → 改密码 → 登出 → 验证旧token失效 → 新密码登录 → 各种错误场景

【如何运行？】
1. 先启动服务（start_dev.bat 或手动 uvicorn）
2. 运行：python test_user_module.py

【为什么每次手机号不同？】
注册的手机号是"唯一"的，第二次运行脚本若还用同一手机号会报"已注册"。
所以用当前时间戳生成一个不重复的手机号，保证脚本可以反复运行。

【关于打印的中文乱码】
Windows 控制台默认编码可能显示乱码，不影响测试结果，
可以看 HTTP 状态码（200=成功，400/401=预期错误）判断是否通过。
"""

import json
import time

import requests  # 发送 HTTP 请求的库（需先安装：pip install requests）

# 后端服务地址（与 start_dev.bat 的端口一致）
BASE = "http://127.0.0.1:8001"


def test():
    # 用当前时间戳生成不重复的手机号
    # 注意：统一使用 199 号段（测试专用），清理时只删 199 号段，绝不触碰真实账号
    phone = f"199{int(time.time()) % 100000000:08d}"

    # ---------- 1. 注册 ----------
    r = requests.post(
        f"{BASE}/api/v1/auth/register",
        json={"phone": phone, "password": "pass123456", "nickname": "爆文创作者"},
    )
    print("register:", r.status_code)
    data = r.json()
    print("  user:", json.dumps(data["user"], ensure_ascii=False))
    token = data["access_token"]  # 取出令牌，后续请求带上
    headers = {"Authorization": f"Bearer {token}"}  # 构造认证请求头

    # ---------- 2. 获取当前用户信息 ----------
    r = requests.get(f"{BASE}/api/v1/auth/me", headers=headers)
    print("me:", r.status_code, json.dumps(r.json(), ensure_ascii=False))

    # ---------- 3. 修改个人资料（只改昵称和简介）----------
    r = requests.put(
        f"{BASE}/api/v1/user/profile",
        headers=headers,
        json={"nickname": "小红书美妆博主小美", "bio": "3万粉丝美妆博主，专注干货分享"},
    )
    print("update profile:", r.status_code, json.dumps(r.json(), ensure_ascii=False))

    # ---------- 4. 修改密码 ----------
    r = requests.put(
        f"{BASE}/api/v1/user/password",
        headers=headers,
        json={"old_password": "pass123456", "new_password": "newpass888"},
    )
    print("change password:", r.status_code, json.dumps(r.json(), ensure_ascii=False))

    # ---------- 5. 登出（销毁 Redis 会话）----------
    r = requests.post(f"{BASE}/api/v1/auth/logout", headers=headers)
    print("logout:", r.status_code, json.dumps(r.json(), ensure_ascii=False))

    # ---------- 6. 验证：登出后旧 token 立即失效 ----------
    # 预期返回 401（会话已失效），证明"登出"真的生效了
    r = requests.get(f"{BASE}/api/v1/auth/me", headers=headers)
    print("me after logout:", r.status_code, r.json())

    # ---------- 7. 用新密码重新登录 ----------
    r = requests.post(
        f"{BASE}/api/v1/auth/login",
        json={"account": phone, "password": "newpass888"},
    )
    print("login with new pwd:", r.status_code)
    token2 = r.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}
    r = requests.get(f"{BASE}/api/v1/auth/me", headers=headers2)
    print("me:", r.status_code, json.dumps(r.json(), ensure_ascii=False))

    # ---------- 8. 错误场景测试 ----------
    # 8.1 重复注册同一个手机号 → 预期 400（该手机号已注册）
    r = requests.post(
        f"{BASE}/api/v1/auth/register",
        json={"phone": phone, "password": "pass123456"},
    )
    print("dup register:", r.status_code, r.json())

    # 8.2 密码错误 → 预期 401（账号或密码错误）
    r = requests.post(
        f"{BASE}/api/v1/auth/login",
        json={"account": phone, "password": "wrongpass"},
    )
    print("wrong pwd login:", r.status_code, r.json())


# 直接运行本文件时执行测试
if __name__ == "__main__":
    test()
