"""
Storage Models - SQLAlchemy ORM 模型

定义所有数据库表结构，使用 PostgreSQL 特性（UUID, JSONB, ARRAY）。
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column, String, Text, Boolean, Float, Integer, 
    ForeignKey, Index, UniqueConstraint, event
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, TIMESTAMP
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


# ============== 用户与会话 ==============

class User(Base):
    """用户表"""
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), nullable=True)
    role = Column(String(20), nullable=False, default='operator')  # admin, operator, viewer
    is_active = Column(Boolean, default=True)
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="owner", cascade="all, delete-orphan")
    results = relationship("MonitoringResult", back_populates="owner", cascade="all, delete-orphan")
    feedbacks = relationship("UserFeedback", back_populates="user", cascade="all, delete-orphan")
    api_configs = relationship("UserApiConfig", back_populates="user", cascade="all, delete-orphan")
    notification_configs = relationship("UserNotificationConfig", back_populates="user", cascade="all, delete-orphan")
    platform_accounts = relationship("UserPlatformAccount", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
    group_memberships = relationship("UserGroupMember", back_populates="user", cascade="all, delete-orphan")
    prompt_templates = relationship("PromptTemplate", back_populates="owner", cascade="all, delete-orphan")


class Session(Base):
    """会话表"""
    __tablename__ = 'sessions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    user_agent = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User", back_populates="sessions")


# ============== 用户组权限 ==============

class UserGroup(Base):
    """用户组表"""
    __tablename__ = 'user_groups'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    members = relationship("UserGroupMember", back_populates="group", cascade="all, delete-orphan")
    permissions = relationship("GroupPermission", back_populates="group", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_user_group_system', 'is_system'),
    )


class UserGroupMember(Base):
    """用户-用户组关联表"""
    __tablename__ = 'user_group_members'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    group_id = Column(UUID(as_uuid=True), ForeignKey('user_groups.id', ondelete='CASCADE'), nullable=False)
    joined_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="group_memberships")
    group = relationship("UserGroup", back_populates="members")

    __table_args__ = (
        UniqueConstraint('user_id', 'group_id', name='uq_user_group_member'),
        Index('idx_user_group_member_user', 'user_id'),
        Index('idx_user_group_member_group', 'group_id'),
    )


class GroupPermission(Base):
    """用户组权限表"""
    __tablename__ = 'group_permissions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey('user_groups.id', ondelete='CASCADE'), nullable=False)
    category = Column(String(32), nullable=False)  # tasks/results/accounts/notify/ai/admin
    enabled = Column(Boolean, default=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    group = relationship("UserGroup", back_populates="permissions")

    __table_args__ = (
        UniqueConstraint('group_id', 'category', name='uq_group_permission'),
        Index('idx_group_permission_group', 'group_id'),
    )


# ============== 任务与结果 ==============

class Task(Base):
    """任务配置表"""
    __tablename__ = 'tasks'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    task_name = Column(String(255), nullable=False)
    order = Column(Integer, default=0)
    enabled = Column(Boolean, default=False)
    keyword = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    max_pages = Column(Integer, default=3)
    personal_only = Column(Boolean, default=True)
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    cron = Column(String(50), nullable=True)
    filters = Column(JSONB, nullable=True)  # 高级筛选条件
    bayes_profile = Column(String(100), default='bayes_v1')
    ai_criteria_id = Column(UUID(as_uuid=True), ForeignKey('ai_criteria.id'), nullable=True)
    bound_account_id = Column(UUID(as_uuid=True), ForeignKey('user_platform_accounts.id'), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    owner = relationship("User", back_populates="tasks")
    results = relationship("MonitoringResult", back_populates="task", cascade="all, delete-orphan")
    ai_criteria = relationship("AiCriteria", back_populates="tasks")
    bound_account = relationship("UserPlatformAccount", back_populates="bound_tasks")
    
    # 唯一约束：同一用户下任务名唯一
    __table_args__ = (
        UniqueConstraint('owner_id', 'task_name', name='uq_task_owner_name'),
        Index('idx_task_owner', 'owner_id'),
    )


class MonitoringResult(Base):
    """监控结果表"""
    __tablename__ = 'monitoring_results'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey('tasks.id', ondelete='CASCADE'), nullable=True)
    item_id = Column(String(50), nullable=False, index=True)
    product_info = Column(JSONB, nullable=True)
    seller_info = Column(JSONB, nullable=True)
    ai_analysis = Column(JSONB, nullable=True)
    ml_precalc = Column(JSONB, nullable=True)
    recommendation_score = Column(Float, nullable=True)
    is_recommended = Column(Boolean, default=False)
    crawled_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # 关系
    owner = relationship("User", back_populates="results")
    task = relationship("Task", back_populates="results")
    feedbacks = relationship("UserFeedback", back_populates="result")
    
    __table_args__ = (
        UniqueConstraint('owner_id', 'item_id', name='uq_result_owner_item'),
        Index('idx_result_owner', 'owner_id'),
        Index('idx_result_task', 'task_id'),
    )


# ============== 贝叶斯相关 ==============

class BayesProfile(Base):
    """贝叶斯配置表"""
    __tablename__ = 'bayes_profiles'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True)  # NULL = 系统默认
    version = Column(String(50), nullable=False)
    display_name = Column(String(100), nullable=True)
    recommendation_fusion = Column(JSONB, nullable=True)
    bayes_feature_rules = Column(JSONB, nullable=True)
    is_default = Column(Boolean, default=False)  # 是否为用户默认配置
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    samples = relationship("BayesSample", back_populates="profile", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('owner_id', 'version', name='uq_bayes_owner_version'),
        Index('idx_bayes_owner', 'owner_id'),
    )


class BayesSample(Base):
    """贝叶斯样本表"""
    __tablename__ = 'bayes_samples'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True)  # NULL = 系统预置
    profile_id = Column(UUID(as_uuid=True), ForeignKey('bayes_profiles.id', ondelete='CASCADE'), nullable=True)
    profile_version = Column(String(50), nullable=False)
    name = Column(String(255), nullable=True)
    vector = Column(ARRAY(Float), nullable=False)
    label = Column(Integer, nullable=False)  # 1=可信, 0=不可信
    source = Column(String(50), default='user')  # 'preset' | 'user'
    item_id = Column(String(50), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # 关系
    profile = relationship("BayesProfile", back_populates="samples")
    
    __table_args__ = (
        Index('idx_sample_owner', 'owner_id'),
        Index('idx_sample_profile', 'profile_id'),
        Index('idx_sample_label', 'label'),
    )


class PromptTemplate(Base):
    """Prompt 模板表"""
    __tablename__ = 'prompt_templates'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True)  # NULL = 系统模板
    name = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="prompt_templates")

    __table_args__ = (
        UniqueConstraint('owner_id', 'name', name='uq_prompt_owner_name'),
        Index('idx_prompt_owner', 'owner_id'),
    )


# ============== 用户反馈 ==============

class UserFeedback(Base):
    """用户反馈表"""
    __tablename__ = 'user_feedbacks'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    result_id = Column(UUID(as_uuid=True), ForeignKey('monitoring_results.id', ondelete='CASCADE'), nullable=False)
    feedback_type = Column(String(20), nullable=False)  # 'trusted' | 'untrusted'
    feature_vector = Column(ARRAY(Float), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User", back_populates="feedbacks")
    result = relationship("MonitoringResult", back_populates="feedbacks")
    
    __table_args__ = (
        Index('idx_feedback_user', 'user_id'),
        Index('idx_feedback_result', 'result_id'),
    )


# ============== AI标准 ==============

class AiCriteria(Base):
    """AI评判标准表"""
    __tablename__ = 'ai_criteria'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True)  # NULL = 系统默认
    name = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)  # 新用户是否默认使用
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    tasks = relationship("Task", back_populates="ai_criteria")
    
    __table_args__ = (
        Index('idx_criteria_owner', 'owner_id'),
    )


# ============== 用户敏感配置 ==============

class UserApiConfig(Base):
    """用户API配置表"""
    __tablename__ = 'user_api_configs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    provider = Column(String(50), nullable=False)  # 'openai' | 'azure' | 'ollama' | 'custom'
    name = Column(String(100), nullable=False)
    api_key_encrypted = Column(Text, nullable=True)  # AES加密
    api_base_url = Column(String(255), nullable=True)
    model = Column(String(100), nullable=True)
    extra_config = Column(JSONB, nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship("User", back_populates="api_configs")
    
    __table_args__ = (
        Index('idx_api_config_user', 'user_id'),
    )


class UserNotificationConfig(Base):
    """用户通知配置表"""
    __tablename__ = 'user_notification_configs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    channel_type = Column(String(50), nullable=False)  # 'ntfy' | 'bark' | 'gotify' | 'webhook' | 'dingtalk'
    name = Column(String(100), nullable=False)
    config_encrypted = Column(Text, nullable=True)  # AES加密的JSON配置
    is_enabled = Column(Boolean, default=True)
    notify_on_complete = Column(Boolean, default=True)
    notify_on_recommend = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship("User", back_populates="notification_configs")
    
    __table_args__ = (
        Index('idx_notify_config_user', 'user_id'),
    )


class UserPlatformAccount(Base):
    """用户平台账号表"""
    __tablename__ = 'user_platform_accounts'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    platform = Column(String(50), nullable=False, default='goofish')  # 闲鱼
    display_name = Column(String(100), nullable=True)
    cookies_encrypted = Column(Text, nullable=True)  # AES加密的Cookie
    risk_control_count = Column(Integer, default=0)
    risk_control_history = Column(JSONB, nullable=True)
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship("User", back_populates="platform_accounts")
    bound_tasks = relationship("Task", back_populates="bound_account")
    
    __table_args__ = (
        Index('idx_platform_account_user', 'user_id'),
    )


# ============== 审计日志 ==============

class AuditLog(Base):
    """审计日志表"""
    __tablename__ = 'audit_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User", back_populates="audit_logs")
    
    __table_args__ = (
        Index('idx_audit_user', 'user_id'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_created', 'created_at'),
    )
