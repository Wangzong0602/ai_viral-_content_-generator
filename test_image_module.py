"""
AI 配图模块自动化测试脚本

【测试内容】
1. 注册用户（拿 token）
2. 调用配图接口 POST /api/v1/content/images/generate
3. 验证返回的本地 URL 可访问（图片真实存在于磁盘）
4. 参数校验测试（count 超范围/未登录）

【如何运行？】
1. 启动后端服务
2. 运行：python test_image_module.py
"""

import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8001"


def test():
    # ---------- 1. 注册用户 ----------
    # 统一使用 199 测试号段（清理时只删该号段，绝不触碰真实账号）
    phone = f"199{int(time.time()) % 100000000:08d}"
    r = requests.post(
        f"{BASE}/api/v1/auth/register",
        json={"phone": phone, "password": "test123456"},
    )
    print("register:", r.status_code)
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # ---------- 2. 配图（2 张，插画风格） ----------
    content = (
        "今天分享 5 个提升效率的 AI 工具，第一个是智能写作助手，"
        "第二个是数据分析神器，第三个是 PPT 生成工具，"
        "第四个是会议纪要转写，第五个是图片处理工具。"
    )
    print("\n开始配图（约需 30-60 秒，请耐心等待）...")
    t0 = time.time()
    r = requests.post(
        f"{BASE}/api/v1/content/images/generate",
        headers=headers,
        json={"content": content, "count": 2, "style": "插画卡通"},
        timeout=300,
    )
    print(f"generate: {r.status_code} 耗时 {time.time() - t0:.0f} 秒")
    data = r.json()
    images = data.get("images", [])
    print(f"  获得 {len(images)} 张图片:")
    for i, img in enumerate(images, 1):
        print(f"  {i}. {img['url']}")

    # ---------- 3. 验证本地 URL 可访问 ----------
    if images:
        url = images[0]["url"]
        r2 = requests.get(f"{BASE}{url}", timeout=30)
        print(f"\n图片访问: {r2.status_code}, 大小 {len(r2.content)} bytes, content-type={r2.headers.get('content-type')}")
        assert r2.status_code == 200, "图片 URL 不可访问！"
        assert r2.headers.get("content-type", "").startswith("image/"), "不是图片类型！"
        print("  ✅ 图片本地存储 + 访问验证通过")

    # ---------- 4. 参数校验测试 ----------
    r = requests.post(
        f"{BASE}/api/v1/content/images/generate",
        headers=headers,
        json={"content": content, "count": 99},  # count 超出 1-5
        timeout=30,
    )
    print(f"\ncount=99 校验: {r.status_code} (预期 422)")
    assert r.status_code == 422

    # 未登录
    r = requests.post(
        f"{BASE}/api/v1/content/images/generate",
        json={"content": content, "count": 1},
        timeout=30,
    )
    print(f"未登录: {r.status_code} (预期 401)")
    assert r.status_code == 401

    print("\n全部配图测试通过！")


if __name__ == "__main__":
    test()
