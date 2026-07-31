"""
配置文件模块（项目所有配置的中心）

【这个文件是干什么的？】
整个项目有很多"可变的配置"：连哪个数据库、连哪个 Redis、JWT 密钥是什么、
token 多久过期……这些信息不应该写死在各个代码文件里（那样改一处要翻遍全项目），
而是集中放在这一个文件统一管理。

【它是怎么工作的？】
1. 我们在项目根目录放了一个 .env 文件（纯文本，一行一个配置）
2. 这里用 pydantic-settings 库，自动读取 .env 文件里的配置
3. .env 里的值会"覆盖"下方定义的默认值
   （例如 .env 里写了 DATABASE_URL=xxx，就会用 xxx，否则用默认值）

【为什么要这样做？】
- 开发环境/生产环境可以有不同的配置，只需要换 .env 文件
- 密钥、密码等敏感信息不写在代码里，避免提交到 git 泄露
"""

from pathlib import Path

# pydantic-settings：让配置类自动从 .env 文件加载配置的库
from pydantic_settings import BaseSettings, SettingsConfigDict

# __file__ 是"当前这个文件"的完整路径
# resolve() 把路径转换成绝对路径，parent 是上一级目录
# 所以 BASE_DIR = 项目根目录（app/core/config.py 向上 3 级 = 项目根目录）
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    配置类：定义项目需要的所有配置项。

    继承 BaseSettings 后，这个类的每个字段都会自动：
    - 从 .env 文件读取同名配置（如 JWT_SECRET_KEY）
    - 如果 .env 没有配置，就使用下方定义的默认值
    """

    # model_config 是 pydantic 的"配置的配置"，说明如何读取
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",  # 指定 .env 文件的位置（项目根目录）
        env_file_encoding="utf-8",  # .env 文件用 UTF-8 编码（支持中文）
        extra="ignore",  # .env 里多出的配置项忽略掉，不报错
    )

    # ---------- 应用基本信息 ----------
    APP_NAME: str = "AI 爆文智能创作平台"  # 应用名称，会显示在接口文档标题上
    APP_VERSION: str = "0.1.0"  # 版本号
    DEBUG: bool = True  # 调试模式：True 时 SQLAlchemy 会打印 SQL 日志

    # ---------- 数据库连接 ----------
    # 格式说明：mysql+pymysql://用户名:密码@主机:端口/库名?charset=utf8mb4
    # - mysql+pymysql：使用 pymysql 驱动连接 MySQL
    # - root:010819：MySQL 用户名和密码
    # - charset=utf8mb4：使用 utf8mb4 字符集（必须！否则存中文会乱码）
    DATABASE_URL: str = (
        "mysql+pymysql://root:010819@127.0.0.1:3306/ai_content_generator?charset=utf8mb4"
    )

    # ---------- Redis 连接 ----------
    # Redis 用来存储"会话"（详见 app/services/session.py）
    # 注意端口是 16379，因为系统把 6379 端口保留了，我们用 16379 代替
    REDIS_URL: str = "redis://127.0.0.1:16379/0"

    # ---------- JWT（登录令牌）配置 ----------
    # JWT 就是一个"加密的字符串"，里面包含了用户 ID 等信息
    # 服务器用它来验证"这个请求是谁发的"，详见 app/core/security.py
    JWT_SECRET_KEY: str = "ai-viral-content-generator-secret-key-change-me"  # 签名密钥（生产环境必须更换！）
    JWT_ALGORITHM: str = "HS256"  # 加密算法
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # token 有效期：60分钟 × 24小时 × 7天 = 7天

    # ---------- 短信服务（预留，尚未使用）----------
    # 文档规划了"手机号 + 验证码"登录，后续对接阿里云短信时需要填写
    SMS_ACCESS_KEY_ID: str = ""
    SMS_ACCESS_KEY_SECRET: str = ""

    # ---------- 通义千问（DashScope 大模型）配置 ----------
    # 阿里云百炼平台的 API Key（https://bailian.console.aliyun.com/ 申请）
    DASHSCOPE_API_KEY: str = ""
    # 通义千问兼容 OpenAI 协议，使用官方兼容模式地址
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # 文本生成模型名称（通义千问系列）
    DASHSCOPE_MODEL: str = "deepseek-v4-flash"


# 创建唯一的配置实例，其他模块通过 `from app.core.config import settings` 使用
# 整个项目共用这一个对象，保证配置读取一次、处处一致
settings = Settings()
