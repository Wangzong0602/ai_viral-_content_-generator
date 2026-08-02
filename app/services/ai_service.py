"""
AI 服务层：统一封装对通义千问（DashScope）的调用

【为什么要单独封装这一层？】
1. 所有智能体都调用大模型，公共逻辑（客户端创建、错误处理、模型选择）集中在这里
2. 以后想换模型（如切换 qwen-max、接入其他厂商），只改这一个文件
3. 智能体代码只关心"提示词"和"怎么用结果"，不用关心底层网络细节

【通义千问为什么能用 openai 库调用？】
阿里云 DashScope 提供了"兼容 OpenAI 协议"的接口：
- 接口地址：https://dashscope.aliyuncs.com/compatible-mode/v1
- 请求/响应格式与 OpenAI 完全一致
所以直接用 openai 官方 SDK，把 base_url 和 api_key 换成阿里的即可，无需额外依赖。

【ChatCompletion 是什么？】
chat.completions.create(...) 是 OpenAI 风格的核心调用：
- model：模型名称（qwen-plus / qwen-max 等）
- messages：对话消息列表，格式为 [{"role": "系统/用户/助手", "content": "..."}]
- 返回响应对象，取 resp.choices[0].message.content 就是模型生成的文本
"""

from openai import OpenAI

from app.core.config import settings

# 全局唯一的 AI 客户端（openai 库内部会管理连接复用，无需每次新建）
# 注意：这里在"模块导入时"就创建客户端，但 API Key 是从配置读取的，
# 所以必须先配置好 .env 再启动服务
ai_client = OpenAI(
    api_key=settings.DASHSCOPE_API_KEY,  # 阿里云百炼申请的密钥
    base_url=settings.DASHSCOPE_BASE_URL,  # 兼容 OpenAI 协议的服务地址
)


def chat_with_search(
    user_prompt: str,
    system_prompt: str = "你是一个智能助手，请基于搜索结果回答用户问题。",
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> str:
    """
    联网搜索对话调用（DashScope 原生 SDK + enable_search 顶层参数）。

    【为什么用原生 SDK 而不是 OpenAI 兼容模式？】
    实测：OpenAI 兼容模式的 extra_body={"enable_search": True} 不生效
    （模型仍按知识库回答，知识截止 2024）。
    而 DashScope 原生 Generation.call 的顶层 enable_search=True 参数
    会真正联网搜索，把实时信息注入回答（实测能正确返回"王虹、邓煜获奖"）。

    【用途（事实真实性保障）】
    - 创作前：搜索用户题材的真实信息，注入创作提示词（方案2）
    - 事实核查：让模型基于联网结果核对生成内容中的事实断言（方案1）

    :param user_prompt: 用户问题/待核查内容
    :param system_prompt: 角色设定
    :param model: 模型名（默认 qwen-plus）
    :param temperature: 温度（核查要低，默认 0.3 保证严谨）
    :param max_tokens: 最大输出
    :return: 模型回答文本
    """
    from dashscope import Generation

    # 联网搜索必须用支持 enable_search 的模型（qwen 系列），
    # 不能用默认的 DASHSCOPE_MODEL（deepseek-v4-flash 不支持搜索，会返回空）
    search_model = model or "qwen-plus"

    # 联网搜索偶发返回空（搜索服务不稳定），重试一次
    for attempt in range(2):
        resp = Generation.call(
            api_key=settings.DASHSCOPE_API_KEY,
            model=search_model,
            prompt=f"{system_prompt}\n\n{user_prompt}",
            enable_search=True,  # 关键：顶层参数开启联网搜索
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if resp.status_code != 200:
            from app.core.exceptions import BizException

            raise BizException(f"联网搜索调用失败: {resp.message}", status_code=502)
        text = resp.output.text if resp.output else ""
        if text and text.strip():
            return text
        # 空结果：重试（第二次尝试去掉 system 前缀，避免过长 prompt）
        if attempt == 0:
            resp = Generation.call(
                api_key=settings.DASHSCOPE_API_KEY,
                model=search_model,
                prompt=user_prompt,
                enable_search=True,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if resp.status_code == 200 and resp.output and resp.output.text:
                return resp.output.text
    return ""


def chat(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """
    通用大模型对话调用（非流式，一次性返回完整结果）。

    :param system_prompt: 系统提示词（定义"角色 + 任务规则"，见各智能体）
    :param user_prompt: 用户提示词（本次要处理的具体内容）
    :param model: 模型名称，默认用配置里的 qwen-plus
    :param temperature: 创造性参数 0-2，越大越天马行空，越小越严谨
    :param max_tokens: 最大生成字数限制（防超时、防烧钱）
    :return: 模型生成的文本
    """
    resp = ai_client.chat.completions.create(
        model=model or settings.DASHSCOPE_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},  # 角色设定
            {"role": "user", "content": user_prompt},  # 具体任务
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


def chat_stream(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
):
    """
    通用大模型流式对话调用（边生成边返回，用于 SSE 实时输出）。

    【流式和一次性有什么区别？】
    一次性调用要等模型"全部生成完"才返回，一篇 2000 字文章可能要等 30 秒+，
    用户盯着空白页以为卡死了。流式调用则一个字一个字"吐"出来，
    前端能实时看到文字在屏幕上生长，体验好得多（打字机效果）。

    【如何使用？】
    这个函数是生成器（有 yield），调用方式：
        for chunk in chat_stream(...):
            print(chunk)  # chunk 是增量文本片段
    内部用 stream=True 让 SDK 进入流式模式，逐块产出增量内容。

    :return: 生成器，每次产出模型生成的"增量文本片段"
    """
    resp = ai_client.chat.completions.create(
        model=model or settings.DASHSCOPE_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,  # 关键：开启流式模式
    )
    for chunk in resp:
        # 流式响应每个 chunk 里通常只有一个增量片段；
        # 结束标志（role 出现或 content 为空）需要跳过
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
