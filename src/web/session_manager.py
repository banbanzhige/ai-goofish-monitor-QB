"""
会话管理器 - 用户会话的存储与管理

负责用户登录会话的CRUD操作，支持：
- 多设备登录管理
- 会话过期自动清理
- 强制登出
- 登录历史记录
"""
import os
import hashlib
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from src.storage import get_storage
from src.web.auth import is_multi_user_mode


# 会话配置
SESSION_EXPIRE_SECONDS = int(os.getenv('SESSION_EXPIRE_SECONDS', 7 * 24 * 60 * 60))
MAX_SESSIONS_PER_USER = int(os.getenv('MAX_SESSIONS_PER_USER', 10))


class SessionManager:
    """用户会话管理器"""
    
    def __init__(self):
        """初始化会话管理器"""
        self.storage = get_storage()
    
    def create_session(
        self,
        user_id: str,
        token: str,
        user_agent: str = None,
        ip_address: str = None
    ) -> Optional[Dict]:
        """
        创建新会话
        
        Args:
            user_id: 用户ID
            token: Session Token
            user_agent: 浏览器/设备信息
            ip_address: 登录IP地址
        
        Returns:
            创建的会话记录或None
        """
        if not is_multi_user_mode():
            return {'id': 'local', 'user_id': user_id}
        
        # 哈希 Token（不存储明文）
        token_hash = self._hash_token(token)
        
        # 计算过期时间
        expires_at = datetime.utcnow() + timedelta(seconds=SESSION_EXPIRE_SECONDS)
        
        session_data = {
            'user_id': user_id,
            'token_hash': token_hash,
            'user_agent': user_agent or '',
            'ip_address': ip_address or '',
            'expires_at': expires_at.isoformat(),
            'created_at': datetime.utcnow().isoformat()
        }
        
        session = self.storage.create_session(session_data)
        
        # 清理过多的会话
        self._cleanup_excess_sessions(user_id)
        
        return session
    
    def validate_session(self, token: str) -> Optional[Dict]:
        """
        验证会话有效性
        
        Args:
            token: Session Token
        
        Returns:
            会话数据（如有效）或 None
        """
        if not is_multi_user_mode():
            return None  # 本地模式使用 auth.py 的验证
        
        token_hash = self._hash_token(token)
        session = self.storage.get_session_by_token_hash(token_hash)
        
        if not session:
            return None
        
        # 检查是否过期
        expires_at = session.get('expires_at')
        if expires_at:
            if isinstance(expires_at, str):
                try:
                    expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                except ValueError:
                    return None
            else:
                expires_dt = expires_at
            
            if datetime.utcnow() > expires_dt.replace(tzinfo=None):
                # 会话已过期，删除它
                self.delete_session(session.get('id'))
                return None
        
        # 更新最后活跃时间（可选）
        self.storage.update_session(session.get('id'), {
            'last_active_at': datetime.utcnow().isoformat()
        })
        
        return session
    
    def delete_session(self, session_id: str) -> bool:
        """
        删除会话（登出）
        
        Args:
            session_id: 会话ID
        
        Returns:
            是否成功
        """
        if not is_multi_user_mode():
            return True
        
        return self.storage.delete_session(session_id)
    
    def delete_session_by_token(self, token: str) -> bool:
        """
        根据Token删除会话
        
        Args:
            token: Session Token
        
        Returns:
            是否成功
        """
        if not is_multi_user_mode():
            return True
        
        token_hash = self._hash_token(token)
        session = self.storage.get_session_by_token_hash(token_hash)
        
        if session:
            return self.delete_session(session.get('id'))
        
        return False
    
    def delete_user_sessions(self, user_id: str, except_current: str = None) -> int:
        """
        删除用户的所有会话（强制登出）
        
        Args:
            user_id: 用户ID
            except_current: 保留的当前会话Token（可选）
        
        Returns:
            删除的会话数量
        """
        if not is_multi_user_mode():
            return 0
        
        sessions = self.get_user_sessions(user_id)
        count = 0
        
        current_hash = self._hash_token(except_current) if except_current else None
        
        for session in sessions:
            # 跳过当前会话
            if current_hash and session.get('token_hash') == current_hash:
                continue
            
            if self.delete_session(session.get('id')):
                count += 1
        
        return count
    
    def get_user_sessions(self, user_id: str) -> List[Dict]:
        """
        获取用户的所有活跃会话
        
        Args:
            user_id: 用户ID
        
        Returns:
            会话列表
        """
        if not is_multi_user_mode():
            return []
        
        return self.storage.get_user_sessions(user_id)
    
    def cleanup_expired_sessions(self) -> int:
        """
        清理所有过期会话
        
        Returns:
            清理的会话数量
        """
        if not is_multi_user_mode():
            return 0
        
        return self.storage.cleanup_expired_sessions()
    
    def extend_session(self, session_id: str, additional_seconds: int = None) -> bool:
        """
        延长会话有效期
        
        Args:
            session_id: 会话ID
            additional_seconds: 延长的秒数（默认使用配置值）
        
        Returns:
            是否成功
        """
        if not is_multi_user_mode():
            return True
        
        seconds = additional_seconds or SESSION_EXPIRE_SECONDS
        new_expires = datetime.utcnow() + timedelta(seconds=seconds)
        
        return self.storage.update_session(session_id, {
            'expires_at': new_expires.isoformat()
        })
    
    def _hash_token(self, token: str) -> str:
        """哈希Token"""
        if not token:
            return ''
        return hashlib.sha256(token.encode()).hexdigest()
    
    def _cleanup_excess_sessions(self, user_id: str):
        """清理超过限制的会话（保留最新的）"""
        sessions = self.get_user_sessions(user_id)
        
        if len(sessions) <= MAX_SESSIONS_PER_USER:
            return
        
        # 按创建时间排序
        sessions.sort(key=lambda s: s.get('created_at', ''), reverse=True)
        
        # 删除旧的会话
        for session in sessions[MAX_SESSIONS_PER_USER:]:
            self.delete_session(session.get('id'))


# 单例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取会话管理器单例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def reset_session_manager():
    """重置会话管理器单例（用于存储后端切换后即时生效）。"""
    global _session_manager
    _session_manager = None
