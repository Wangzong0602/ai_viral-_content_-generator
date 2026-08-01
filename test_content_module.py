"""
内容创作模块全流程测试脚本

【测试内容】
1. 注册用户（拿 token）
2. 生成选题（POST /content/topics）
3. SSE 完整创作（GET /content/generate）——解析流式事件，验证：
   - 收到 progress 事件（各智能体进度）
   - 收到 content 事件（正文增量）
   - 收到 complete 事件（最终结果 + 任务ID）
4. 历史记录列表 / 详情

【如何运行？】
1. 先启动服务
2. 运行：python test_content_module.py

【SSE 响应解析说明】
SSE 格式：
    event: progress
    data: {"step": "logic", ...}
    <空行>
每个事件由空行分隔。本脚本按行读取，分别提取 event 行和 data 行。
"""

import json
import sys
import time

import requests

# Windows 控制台默认 GBK 编码，打印 emoji 等字符会报错，强制用 UTF-8 输出
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8001"


def parse_sse(text: str) -> list[dict]:
    """
    把 SSE 响应文本解析成事件列表。

    SSE 协议：事件之间用空行（\n\n）分隔。
    每个事件可能有多行，我们只关心 event: 和 data: 开头的行。
    """
    events = []
    # 按空行分割成一个个事件块（split("\n\n") 正好对应 SSE 的事件分隔）
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        current = {}
        for line in block.split("\n"):
            if line.startswith("event:"):
                current["event"] = line[6:].strip()  # 去掉 "event:" 前缀
            elif line.startswith("data:"):
                current["data"] = line[5:].strip()  # 去掉 "data:" 前缀
        if current:
            events.append(current)
    return events


def test():
    # ---------- 1. 注册用户 ----------
    # 统一使用 199 测试号段（清理时只删该号段，绝不触碰真实账号）
    phone = f"199{int(time.time()) % 100000000:08d}"
    r = requests.post(
        f"{BASE}/api/v1/auth/register",
        json={"phone": phone, "password": "pass123456"},
    )
    print("register:", r.status_code)
    token = r.json()["access_token"]

    # ---------- 2. 生成选题 ----------
    r = requests.post(
        f"{BASE}/api/v1/content/topics",
        headers={"Authorization": f"Bearer {token}"},
        json={"keyword": "AI工具提升效率", "platform": "小红书"},
    )
    print("topics:", r.status_code)
    topics = r.json()["topics"]
    print(f"  获得 {len(topics)} 个选题:")
    for i, t in enumerate(topics, 1):
        print(f"  {i}. {t['title']}")
    if not topics:
        print("  [失败] 选题为空")
        return
    selected = topics[0]["title"]

    # ---------- 3. SSE 完整创作 ----------
    print("\n开始流式创作（会持续数十秒，请耐心等待）...")
    url = (
        f"{BASE}/api/v1/content/generate"
        f"?keyword=AI工具提升效率&platform=小红书"
        f"&selected_title={requests.utils.quote(selected)}&token={token}"
    )
    start = time.time()
    r = requests.get(url, stream=True, timeout=300)
    print("generate status:", r.status_code)

    # 读取全部流式内容（直接用 text，避免 iter_lines 吞空行导致事件无法分隔）
    raw_text = r.text

    events = parse_sse(raw_text)
    print(f"  收到 {len(events)} 个事件，耗时 {time.time() - start:.0f} 秒")

    # 统计各类事件
    from collections import Counter

    counter = Counter(e["event"] for e in events)
    print("  事件类型分布:", dict(counter))

    # 验证 progress 事件（应包含 5 个智能体步骤）
    progress_steps = [
        json.loads(e["data"])["step"]
        for e in events
        if e["event"] == "progress" and '"step"' in e["data"]
    ]
    print("  智能体步骤:", progress_steps)

    # 验证 complete 事件
    complete = [e for e in events if e["event"] == "complete"]
    if complete:
        result = json.loads(complete[0]["data"])
        task_id = result["task_id"]
        content = result["content"]
        print(f"  创作完成！task_id={task_id}, 正文长度={len(content)} 字")
        print(f"  敏感词报告: {result['sensitive_report']}")
        print(f"  正文前100字: {content[:100]}")
    else:
        error = [e for e in events if e["event"] == "error"]
        print("  [失败] 未收到 complete 事件")
        if error:
            print("  错误:", json.loads(error[0]["data"])["detail"])
        return

    # ---------- 4. 历史记录 ----------
    r = requests.get(
        f"{BASE}/api/v1/content/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    print("\ntasks list:", r.status_code, f"共 {len(r.json())} 条记录")

    r = requests.get(
        f"{BASE}/api/v1/content/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    print("task detail:", r.status_code, "标题:", r.json()["selected_title"][:30])

    # ---------- 5. 权限测试：未登录访问 ----------
    r = requests.get(f"{BASE}/api/v1/content/tasks")
    print("no-auth tasks:", r.status_code, "(预期 401)")


if __name__ == "__main__":
    test()
