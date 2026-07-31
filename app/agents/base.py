"""
智能体公共模块：存放所有智能体共用的工具函数

【智能体的整体设计思路】
每个智能体 = "一个角色定位（system prompt）+ 一个具体任务（user prompt）"
- 通过精心设计的提示词，让大模型扮演某个专家角色（选题策划师、文案编辑……）
- 输入上一步的结果，输出本环节的成果
- 一步步串联起来，就形成了完整的创作流水线：
  选题 → 爆文逻辑分析 → 文案创作 → 润色 → 排版
"""

import json
import re


def extract_json(text: str) -> dict:
    """
    从大模型输出中提取 JSON 对象。

    【为什么要做这个清洗？】
    大模型虽然被要求"只输出 JSON"，但偶尔会：
    - 前后夹杂解释文字（如"以下是结果："）
    - 输出被 ```json ... ``` 代码块包裹（Markdown 格式）
    - 花括号被转义成 {{ }}（企业级容错：有些模型会这样输出）

    【处理步骤】
    1. 尝试直接解析（大多数情况一次成功）
    2. 失败 → 把 {{ 还原为 {、}} 还原为 } 再解析（容错转义）
    3. 再失败 → 用正则找第一对 { } 之间的内容再解析
    4. 还是失败 → 返回空字典（调用方需要自行处理缺失字段，不至于崩溃）
    """
    text = text.strip()

    # 第一步：直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 第二步：容错转义（{{ }} → { }）
    try:
        return json.loads(text.replace("{{", "{").replace("}}", "}"))
    except json.JSONDecodeError:
        pass

    # 第三步：正则提取最像 JSON 的部分
    # 非贪婪匹配：找第一个 { 到最后一个 } 之间的内容
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}
