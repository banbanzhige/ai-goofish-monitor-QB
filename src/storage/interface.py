"""
Storage Interface - 存储抽象接口

定义所有存储后端必须实现的接口方法。
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime


class StorageInterface(ABC):
    """
    统一存储接口
    
    所有存储后端（本地文件、PostgreSQL等）必须实现此接口。
    """
    
    # ============== 用户管理 ==============
    
    @abstractmethod
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取用户"""
        pass
    
    @abstractmethod
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户"""
        pass
    
    @abstractmethod
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新用户"""
        pass
    
    @abstractmethod
    def update_user(self, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新用户信息"""
        pass
    
    @abstractmethod
    def list_users(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """获取用户列表"""
        pass
    
    @abstractmethod
    def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        pass

    # ============== 用户组管理 ==============

    @abstractmethod
    def create_user_group(self, group_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建用户组"""
        pass

    @abstractmethod
    def get_user_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取用户组"""
        pass

    @abstractmethod
    def list_user_groups(self) -> List[Dict[str, Any]]:
        """获取用户组列表"""
        pass

    @abstractmethod
    def update_user_group(self, group_id: str, group_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新用户组"""
        pass

    @abstractmethod
    def delete_user_group(self, group_id: str) -> bool:
        """删除用户组"""
        pass

    @abstractmethod
    def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户所属组列表"""
        pass

    @abstractmethod
    def set_user_groups(self, user_id: str, group_ids: List[str]) -> bool:
        """覆盖设置用户所属组"""
        pass

    @abstractmethod
    def get_group_permissions(self, group_id: str) -> List[Dict[str, Any]]:
        """获取用户组权限"""
        pass

    @abstractmethod
    def set_group_permissions(self, group_id: str, categories: Dict[str, bool]) -> bool:
        """设置用户组权限"""
        pass
    
    # ============== 会话管理 ==============
    
    @abstractmethod
    def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建会话"""
        pass
    
    @abstractmethod
    def get_session_by_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """根据token哈希获取会话"""
        pass
    
    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        pass
    
    @abstractmethod
    def delete_user_sessions(self, user_id: str) -> int:
        """删除用户的所有会话"""
        pass
    
    # ============== 任务管理 ==============
    
    @abstractmethod
    def get_tasks(self, owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取任务列表，可按所有者筛选"""
        pass
    
    @abstractmethod
    def get_task_by_name(self, task_name: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """根据任务名获取任务"""
        pass
    
    @abstractmethod
    def save_task(self, task: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存任务（创建或更新）"""
        pass
    
    @abstractmethod
    def delete_task(self, task_name: str, owner_id: Optional[str] = None) -> bool:
        """删除任务"""
        pass
    
    @abstractmethod
    def update_task_order(self, ordered_names: List[str], owner_id: Optional[str] = None) -> bool:
        """更新任务排序"""
        pass
    
    # ============== 监控结果管理 ==============
    
    @abstractmethod
    def save_result(self, task_name: str, result: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存监控结果"""
        pass
    
    @abstractmethod
    def get_results(
        self, 
        task_name: str, 
        owner_id: Optional[str] = None,
        limit: int = 100, 
        offset: int = 0,
        recommended_only: bool = False,
        keyword: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取监控结果列表"""
        pass
    
    @abstractmethod
    def get_result_by_item_id(self, item_id: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """根据商品ID获取结果"""
        pass

    @abstractmethod
    def result_exists(
        self,
        item_id: str,
        owner_id: Optional[str] = None,
        task_name: Optional[str] = None
    ) -> bool:
        """检查结果是否已存在"""
        pass

    @abstractmethod
    def save_result_if_absent(
        self,
        task_name: str,
        result_data: Dict[str, Any],
        owner_id: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """幂等保存结果，返回(结果数据, 是否新建)"""
        pass
    
    @abstractmethod
    def delete_results(
        self, 
        task_name: str, 
        owner_id: Optional[str] = None,
        item_ids: Optional[List[str]] = None
    ) -> int:
        """删除监控结果，返回删除数量"""
        pass
    
    # ============== 贝叶斯配置管理 ==============
    
    @abstractmethod
    def get_bayes_profile(self, version: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取贝叶斯配置"""
        pass
    
    @abstractmethod
    def save_bayes_profile(self, profile: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存贝叶斯配置"""
        pass
    
    @abstractmethod
    def list_bayes_profiles(self, owner_id: Optional[str] = None, include_system: bool = True) -> List[Dict[str, Any]]:
        """获取贝叶斯配置列表"""
        pass
    
    # ============== 贝叶斯样本管理 ==============
    
    @abstractmethod
    def get_bayes_samples(
        self, 
        profile_version: str, 
        owner_id: Optional[str] = None,
        label: Optional[int] = None,
        include_system: bool = True
    ) -> List[Dict[str, Any]]:
        """获取贝叶斯样本"""
        pass
    
    @abstractmethod
    def add_bayes_sample(self, sample: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """添加贝叶斯样本"""
        pass
    
    @abstractmethod
    def delete_bayes_sample(self, sample_id: str, owner_id: Optional[str] = None) -> bool:
        """删除贝叶斯样本"""
        pass
    
    # ============== 用户反馈管理 ==============
    
    @abstractmethod
    def save_feedback(
        self, 
        user_id: str,
        result_id: str, 
        feedback_type: str, 
        feature_vector: List[float]
    ) -> Dict[str, Any]:
        """保存用户反馈"""
        pass
    
    @abstractmethod
    def get_feedbacks(
        self, 
        user_id: Optional[str] = None,
        result_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取用户反馈列表"""
        pass
    
    @abstractmethod
    def delete_feedback(
        self,
        user_id: str,
        result_id: str
    ) -> bool:
        """删除指定结果的用户反馈，返回是否成功"""
        pass
    
    # ============== AI标准管理 ==============
    
    @abstractmethod
    def get_ai_criteria(self, criteria_id: str) -> Optional[Dict[str, Any]]:
        """获取AI标准"""
        pass
    
    @abstractmethod
    def list_ai_criteria(self, owner_id: Optional[str] = None, include_system: bool = True) -> List[Dict[str, Any]]:
        """获取AI标准列表"""
        pass
    
    @abstractmethod
    def save_ai_criteria(self, criteria: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存AI标准"""
        pass
    
    @abstractmethod
    def delete_ai_criteria(self, criteria_id: str, owner_id: Optional[str] = None) -> bool:
        """删除AI标准"""
        pass
    
    # ============== 用户API配置管理 ==============
    
    @abstractmethod
    def get_user_api_configs(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的API配置列表"""
        pass
    
    @abstractmethod
    def save_user_api_config(self, user_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """保存用户API配置"""
        pass
    
    @abstractmethod
    def delete_user_api_config(self, config_id: str, user_id: str) -> bool:
        """删除用户API配置"""
        pass
    
    @abstractmethod
    def get_default_api_config(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户默认API配置，如无则返回系统配置"""
        pass
    
    # ============== 用户通知配置管理 ==============
    
    @abstractmethod
    def get_user_notification_configs(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的通知配置列表"""
        pass
    
    @abstractmethod
    def save_user_notification_config(self, user_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """保存用户通知配置"""
        pass
    
    @abstractmethod
    def delete_user_notification_config(self, config_id: str, user_id: str) -> bool:
        """删除用户通知配置"""
        pass
    
    # ============== 用户平台账号管理 ==============
    
    @abstractmethod
    def get_user_platform_accounts(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的平台账号列表"""
        pass
    
    @abstractmethod
    def save_user_platform_account(self, user_id: str, account: Dict[str, Any]) -> Dict[str, Any]:
        """保存用户平台账号"""
        pass
    
    @abstractmethod
    def delete_user_platform_account(self, account_id: str, user_id: str) -> bool:
        """删除用户平台账号"""
        pass
    
    @abstractmethod
    def update_platform_account_cookies(self, account_id: str, user_id: str, cookies: str) -> bool:
        """更新平台账号Cookie"""
        pass
    
    # ============== 审计日志 ==============
    
    @abstractmethod
    def log_audit(
        self, 
        user_id: str, 
        action: str, 
        resource_type: str, 
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """记录审计日志"""
        pass
    
    @abstractmethod
    def get_audit_logs(
        self, 
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取审计日志"""
        pass
