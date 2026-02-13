"""
Storage Utilities - 加密和辅助工具

提供敏感数据加密/解密功能和其他工具函数。
"""

import os
import hashlib
import base64
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def get_master_key() -> bytes:
    """
    获取主密钥
    
    从环境变量 ENCRYPTION_MASTER_KEY 获取，如果不存在则使用默认值。
    生产环境必须设置此环境变量！
    
    Returns:
        bytes: 32字节的密钥
    """
    key = os.getenv('ENCRYPTION_MASTER_KEY', 'default-encryption-key-change-in-production')
    # 使用SHA256确保密钥长度
    return hashlib.sha256(key.encode()).digest()


def derive_user_key(user_id: str) -> bytes:
    """
    为用户派生独立的加密密钥
    
    使用 PBKDF2 从主密钥和用户ID派生用户专属密钥。
    
    Args:
        user_id: 用户ID
        
    Returns:
        bytes: Fernet兼容的base64编码密钥
    """
    master_key = get_master_key()
    salt = user_id.encode()
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = kdf.derive(master_key)
    return base64.urlsafe_b64encode(key)


def get_user_cipher(user_id: str) -> Fernet:
    """
    获取用户专属的加密器
    
    Args:
        user_id: 用户ID
        
    Returns:
        Fernet: 加密器实例
    """
    user_key = derive_user_key(user_id)
    return Fernet(user_key)


def encrypt_sensitive(user_id: str, data: str) -> str:
    """
    加密敏感数据
    
    Args:
        user_id: 用户ID（用于派生密钥）
        data: 要加密的数据
        
    Returns:
        str: 加密后的base64字符串
    """
    if not data:
        return ""
    cipher = get_user_cipher(user_id)
    encrypted = cipher.encrypt(data.encode('utf-8'))
    return encrypted.decode('utf-8')


def decrypt_sensitive(user_id: str, encrypted: str) -> str:
    """
    解密敏感数据
    
    Args:
        user_id: 用户ID（用于派生密钥）
        encrypted: 加密的数据
        
    Returns:
        str: 解密后的原始数据
    """
    if not encrypted:
        return ""
    cipher = get_user_cipher(user_id)
    decrypted = cipher.decrypt(encrypted.encode('utf-8'))
    return decrypted.decode('utf-8')


def hash_token(token: str) -> str:
    """
    计算token的SHA256哈希
    
    用于会话token的安全存储。
    
    Args:
        token: 原始token
        
    Returns:
        str: 64字符的十六进制哈希值
    """
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    """
    密码哈希
    
    使用bcrypt进行密码哈希。
    
    Args:
        password: 原始密码
        
    Returns:
        str: bcrypt哈希值
    """
    import bcrypt
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """
    验证密码
    
    Args:
        password: 原始密码
        hashed: bcrypt哈希值
        
    Returns:
        bool: 密码是否匹配
    """
    import bcrypt
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def generate_uuid() -> str:
    """生成UUID字符串"""
    import uuid
    return str(uuid.uuid4())
