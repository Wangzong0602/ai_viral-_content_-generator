"""
项目统一日志模块

【为什么需要统一 logger？】
1. 全项目日志格式一致（时间/级别/模块名/消息），方便排查问题
2. 日志同时输出到控制台和文件（文件留档，排查历史问题）
3. 禁止 print：print 没有级别、没有时间戳、无法关闭，
   logger 支持 DEBUG/INFO/WARNING/ERROR 分级控制

【用法】
from app.core.logger import logger
logger.info("用户注册成功, user_id=%s", user_id)
logger.error("生成图片失败: %s", exc)

注意：logger 的消息参数用 %s 占位符（lazy 格式化），
避免即使日志级别不输出也浪费拼接性能。
"""

import logging
import sys
from pathlib import Path

# 日志文件存放目录（项目根目录 /logs）
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"


def _build_logger() -> logging.Logger:
    """构建并返回项目全局日志器（单例）。"""
    # 确保日志目录存在
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("ai_content_generator")
    logger.setLevel(logging.DEBUG)  # 全局级别：DEBUG 及以上都记录

    # 避免重复添加 handler（模块可能被多次 import）
    if logger.handlers:
        return logger

    # ---------- 格式：时间 | 级别 | 模块:行号 | 消息 ----------
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ---------- 1. 控制台输出 ----------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # 控制台只显示 INFO 及以上（避免刷屏）
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ---------- 2. 文件输出（滚动日志，保留 7 天） ----------
    # RotatingFileHandler：日志文件超过 10MB 自动轮转
    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=7,  # 保留 7 个历史文件
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # 文件记录全部级别（详细排查用）
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# 全局唯一实例：所有模块 `from app.core.logger import logger` 使用同一个
logger = _build_logger()
