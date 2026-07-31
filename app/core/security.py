"""
安全模块：密码加密 + JWT 令牌生成/校验

【先理解两个核心概念】

1. 密码为什么不能明文存数据库？
   如果数据库被拖库，所有用户的密码就泄露了。所以我们要"哈希"密码：
   - 哈希 = 把任意长度的密码通过算法变成一个固定长度的"指纹"字符串
   - bcrypt 哈希的特点：
     a. 不可逆：从哈希值无法反推出原密码（这是设计目标）
     b. 每次哈希结果都不同（自动加随机盐），防止两个相同密码哈希一致
     c. 校验方式：把"明文密码 + 存储的哈希"交给 bcrypt.checkpw 验证是否匹配
   所以数据库里永远只存哈希，不存明文。

2. JWT 是什么？
   JWT（JSON Web Token）是一个"自包含"的令牌字符串，结构为：xxx.yyy.zzz
   - xxx：头部（用什么算法）
   - yyy：载荷（放自定义数据，比如 user_id）
   - zzz：签名（用密钥把前两部分加密，防篡改）
   服务端用"密钥"生成签名，客户端拿着 token 来访问，
   服务端用同一个密钥验证签名没被篡改，就信任 token 里写的 user_id。
   因为 token 里已含用户身份信息，所以服务端"不需要查数据库"就知道是谁——这就是 JWT 的核心价值。

【登录流程回顾】
注册/登录成功 → create_access_token(用户id) 生成 token → 返回给前端
用户后续请求 → 前端带上 token → deps.py 里 decode_token 解析出用户id
"""

from datetime import datetime, timedelta, timezone

import bcrypt  # 密码哈希库（比 passlib 更底层、更稳定，我们直接用它）
import jwt  # PyJWT：生成和解析 JWT 令牌的库

from app.core.config import settings


def hash_password(password: str) -> str:
    """
    对明文密码进行 bcrypt 哈希加密，返回加密后的字符串。

    逻辑拆解（从里到外）：
    1. password.encode("utf-8")：把字符串转成字节（bcrypt 只处理字节）
    2. bcrypt.gensalt()：生成一个随机的"盐"（一串随机字符，让哈希更安全）
    3. bcrypt.hashpw(密码字节, 盐)：执行哈希计算，得到加密结果（字节）
    4. .decode("utf-8")：把结果转回字符串，方便存数据库

    :param password: 用户输入的明文密码
    :return: 加密后的哈希字符串（存数据库的就是它）
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    校验"用户输入的密码"和"数据库存的哈希"是否匹配。

    为什么这么设计？
    - 因为哈希不可逆，我们无法把哈希解密成原密码来对比
    - 只能反过来：用 checkpw 把"明文"和"哈希"重新算一遍，
      如果算法一致且密码正确，就会返回 True
    - 盐已经包含在哈希字符串里，checkpw 会自动提取，无需我们操心

    :param plain_password: 用户登录时输入的明文密码
    :param hashed_password: 注册时存进数据库的哈希字符串
    :return: 匹配返回 True，不匹配返回 False
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),  # 明文密码转字节
            hashed_password.encode("utf-8"),  # 存储的哈希转字节
        )
    except ValueError:
        # ValueError 通常表示"哈希格式不合法"（比如库里的数据被改坏了）
        # 这种情况视为验证失败，而不是让程序崩溃
        return False


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """
    生成 JWT 令牌。

    【逻辑说明】
    1. 先算出过期时间：当前时间 + 有效期（默认 7 天）
    2. 构造载荷 payload：
       - "sub"：JWT 标准字段（Subject 主题），我们放用户 ID，用字符串
       - "exp"：JWT 标准字段（Expiration 过期时间），必须是 UTC 时间
    3. jwt.encode 用密钥签名加密，生成最终令牌

    【为什么用 UTC 时间？】
    不同电脑/服务器时区可能不同（东八区、UTC、美国东部……）。
    如果各自用本地时间，过期时间就乱套了。
    统一用 UTC（世界标准时间）就完全一致。
    这里特意加 timezone.utc 生成"带时区的时间"，避免 Python 警告。

    :param subject: 令牌的主题，我们传用户 ID（如 "1"）
    :param expires_minutes: 自定义有效期（分钟），不传就用配置的默认值
    :return: 完整的 JWT 令牌字符串
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    解析并验证 JWT 令牌。

    【为什么叫"验证"而不是简单的"解码"？】
    jwt.decode 内部会做三件事：
    1. 用密钥检查签名是否正确 → 防止别人伪造令牌
    2. 检查 exp 是否过期 → 过期的令牌直接报错
    3. 解析出载荷内容返回

    如果签名被篡改或令牌过期，会抛出异常，
    由调用方（app/api/deps.py）捕获并返回 401 未授权。

    :param token: 前端传来的 JWT 字符串
    :return: 令牌中的载荷字典，如 {"sub": "1", "exp": 1750000000}
    :raises: jwt 库的各种异常（InvalidTokenError、ExpiredSignatureError 等）
    """
    return jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
