"""
图像生成服务：支持通义万相系列模型
- wanx2.1-t2i-turbo: 快速低质量（旧版 API）
- wan2.7-image-pro: 高质量（新版 messages API）
"""

import asyncio
import httpx
from typing import Optional
from app.core.config import settings
from app.core.logger import logger
from app.services.image_storage import download_and_save


class ImageGenerationService:
    """图像生成服务"""
    
    # 模型配置
    MODELS = {
        "wanx2.1-t2i-turbo": {
            "endpoint": "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
            "format": "legacy",  # 旧版格式
        },
        "wan2.7-image-pro": {
            "endpoint": "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
            "format": "messages",  # 新版 messages 格式
        },
    }
    
    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
    
    async def generate(
        self,
        prompt: str,
        size: str = "1024*1024",
        n: int = 1,
        model: str | None = None,
        negative_prompt: str | None = None,
    ) -> list[str]:
        """
        生成图像
        
        Args:
            prompt: 提示词
            size: 尺寸（如 "1024*1024"）
            n: 生成数量
            model: 模型名称（默认使用配置中的 DASHSCOPE_IMAGE_MODEL）
            negative_prompt: 负面提示词（告诉模型避免什么，降低AI味）
            
        Returns:
            本地图片 URL 列表
        """
        model = model or settings.DASHSCOPE_IMAGE_MODEL
        config = self.MODELS.get(model)
        
        if not config:
            raise ValueError(f"不支持的模型: {model}")
        
        logger.info(f"开始生成图像: model={model}, size={size}, n={n}")
        logger.debug(f"Prompt: {prompt[:100]}...")
        
        if config["format"] == "legacy":
            return await self._generate_legacy(prompt, size, n, model)
        elif config["format"] == "messages":
            return await self._generate_messages(prompt, size, n, model, negative_prompt)
        else:
            raise ValueError(f"未知的格式类型: {config['format']}")
    
    async def _generate_legacy(
        self,
        prompt: str,
        size: str,
        n: int,
        model: str,
    ) -> list[str]:
        """旧版 API（wanx2.1-t2i-turbo）"""
        # 这里可以用 dashscope SDK，保持原有逻辑
        from dashscope import ImageSynthesis
        
        logger.info(f"使用旧版 API: {model}")
        
        def call():
            return ImageSynthesis.call(
                model=model,
                prompt=prompt,
                size=size,
                n=n,
            )
        
        result = await asyncio.to_thread(call)
        
        if result.status_code != 200:
            logger.error(f"图像生成失败: {result.code} - {result.message}")
            raise Exception(f"图像生成失败: {result.message}")
        
        remote_urls = [item.url for item in result.output.results]
        logger.info(f"远程图像生成成功: {len(remote_urls)} 张")
        
        # 下载并保存到本地
        local_urls = []
        for url in remote_urls:
            local_url = await download_and_save(url)
            local_urls.append(local_url)
        
        return local_urls
    
    async def _generate_messages(
        self,
        prompt: str,
        size: str,
        n: int,
        model: str,
        negative_prompt: str | None = None,
    ) -> list[str]:
        """新版 messages API（wan2.7-image-pro）"""
        endpoint = self.MODELS[model]["endpoint"]
        
        logger.info(f"使用 messages API: {model}")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        
        # 负面提示词：wan2.7-image-pro 要求 messages 恰好 1 条，
        # 所以把负面提示词合并进第一条消息的文本里（用指令方式表达）
        full_text = prompt
        if negative_prompt:
            full_text = f"{prompt}\n\n【避免】{negative_prompt}"
        
        payload = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": full_text}],
                    }
                ],
            },
            "parameters": {
                "size": size,
                "n": n,
            }
        }
        
        async with httpx.AsyncClient(timeout=60) as client:
            # 提交任务
            resp = await client.post(endpoint, headers=headers, json=payload)
            
            if resp.status_code != 200:
                logger.error(f"任务提交失败: {resp.status_code} - {resp.text[:200]}")
                raise Exception(f"任务提交失败: {resp.status_code}")
            
            task_id = resp.json().get("output", {}).get("task_id")
            if not task_id:
                logger.error(f"未获取到 task_id: {resp.text[:200]}")
                raise Exception("未获取到 task_id")
            
            logger.info(f"任务已提交: task_id={task_id}")
            
            # 轮询任务状态
            check_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
            max_attempts = 30  # 最多等待 60 秒
            
            for attempt in range(max_attempts):
                await asyncio.sleep(2)
                
                check_resp = await client.get(
                    check_url,
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                status_data = check_resp.json()
                status = status_data.get("output", {}).get("task_status")
                
                if status == "SUCCEEDED":
                    # 提取图像 URL
                    choices = status_data.get("output", {}).get("choices", [])
                    remote_urls = []
                    
                    for choice in choices:
                        content = choice.get("message", {}).get("content", [])
                        for item in content:
                            if item.get("type") == "image" and item.get("image"):
                                remote_urls.append(item["image"])
                    
                    logger.info(f"图像生成成功: {len(remote_urls)} 张")
                    
                    # 下载并保存到本地
                    local_urls = []
                    for url in remote_urls:
                        local_url = await download_and_save(url)
                        local_urls.append(local_url)
                    
                    return local_urls
                
                elif status == "FAILED":
                    error_msg = status_data.get("output", {}).get("message", "未知错误")
                    logger.error(f"任务失败: {error_msg}")
                    raise Exception(f"图像生成失败: {error_msg}")
                
                else:
                    logger.debug(f"任务进行中: {status} (attempt {attempt + 1}/{max_attempts})")
            
            raise Exception("图像生成超时")


# 全局服务实例
image_generation_service = ImageGenerationService()
