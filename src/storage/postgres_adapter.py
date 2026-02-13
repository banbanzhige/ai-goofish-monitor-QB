"""
PostgreSQL Storage Adapter - PostgreSQL 数据库存储适配器

实现 StorageInterface，使用 SQLAlchemy ORM 操作 PostgreSQL 数据库。
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker, Session as DBSession
from sqlalchemy.exc import IntegrityError

from .interface import StorageInterface
from .models import (
    Base, User, Session, Task, MonitoringResult,
    BayesProfile, BayesSample, UserFeedback, AiCriteria,
    UserApiConfig, UserNotificationConfig, UserPlatformAccount, AuditLog,
    UserGroup, UserGroupMember, GroupPermission
)
from .utils import (
    hash_password, verify_password, hash_token, generate_uuid,
    encrypt_sensitive, decrypt_sensitive
)
from src.config import WEB_USERNAME, WEB_PASSWORD


class PostgresAdapter(StorageInterface):
    """
    PostgreSQL 存储适配器
    
    使用 SQLAlchemy ORM 实现完整的多用户数据隔离功能。
    """
    PERMISSION_CATEGORIES = ("tasks", "results", "accounts", "notify", "ai", "admin")
    SYSTEM_GROUP_DEFINITIONS = (
        {
            "code": "super_admin_group",
            "name": "超级管理员组",
            "description": "系统预置：全量权限",
            "is_system": True,
            "categories": {"tasks": True, "results": True, "accounts": True, "notify": True, "ai": True, "admin": True},
        },
        {
            "code": "admin_group",
            "name": "系统管理员组",
            "description": "系统预置：管理权限",
            "is_system": True,
            "categories": {"tasks": True, "results": True, "accounts": True, "notify": True, "ai": True, "admin": True},
        },
        {
            "code": "operator_group",
            "name": "操作员组",
            "description": "系统预置：日常运营权限",
            "is_system": True,
            "categories": {"tasks": True, "results": True, "accounts": True, "notify": True, "ai": False, "admin": False},
        },
        {
            "code": "viewer_group",
            "name": "查看者组",
            "description": "系统预置：只读权限",
            "is_system": True,
            "categories": {"tasks": False, "results": True, "accounts": False, "notify": False, "ai": False, "admin": False},
        },
    )
    ROLE_TO_SYSTEM_GROUP_CODE = {
        "super_admin": "super_admin_group",
        "admin": "admin_group",
        "operator": "operator_group",
        "viewer": "viewer_group",
    }
    
    def __init__(self, database_url: str, echo: bool = False):
        """
        初始化 PostgreSQL 适配器
        
        Args:
            database_url: 数据库连接URL，格式: postgresql://user:pass@host:port/dbname
            echo: 是否打印SQL语句（调试用）
        """
        self.engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            echo=echo
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.project_root = Path(__file__).resolve().parent.parent.parent
    
    def create_tables(self):
        """创建所有数据库表"""
        Base.metadata.create_all(bind=self.engine)
        with self.get_session() as session:
            self._ensure_system_groups(session)
            self._ensure_system_ai_criteria(session)
            self._ensure_default_super_admin(session)
    
    def drop_tables(self):
        """删除所有数据库表（危险操作，仅用于测试）"""
        Base.metadata.drop_all(bind=self.engine)
    
    @contextmanager
    def get_session(self):
        """获取数据库会话的上下文管理器"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def _to_dict(self, obj, exclude: List[str] = None) -> Dict[str, Any]:
        """将 ORM 对象转换为字典"""
        if obj is None:
            return None
        
        exclude = exclude or []
        result = {}
        
        for column in obj.__table__.columns:
            if column.name in exclude:
                continue
            value = getattr(obj, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif hasattr(value, 'hex'):  # UUID
                value = str(value)
            result[column.name] = value
        
        return result

    def _split_task_payload(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """拆分任务数据，将未知字段收敛到 filters 中"""
        allowed_keys = {column.name for column in Task.__table__.columns}
        base_data: Dict[str, Any] = {}
        extra_data: Dict[str, Any] = {}

        for key, value in task_data.items():
            if key in allowed_keys:
                base_data[key] = value
            else:
                extra_data[key] = value

        filters_value = base_data.get("filters")
        filters_data = filters_value if isinstance(filters_value, dict) else {}
        if extra_data:
            filters_data = {**filters_data, **extra_data}
            base_data["filters"] = filters_data

        return base_data

    def _merge_task_filters(self, task_dict: Dict[str, Any]) -> Dict[str, Any]:
        """将 filters 中的扩展字段合并回任务字典，保持旧字段兼容"""
        allowed_keys = {column.name for column in Task.__table__.columns}
        filters_value = task_dict.get("filters")
        if isinstance(filters_value, dict):
            for key, value in filters_value.items():
                if key not in allowed_keys and key not in task_dict:
                    task_dict[key] = value
        return task_dict

    def _build_group_payload(self, group: UserGroup, permissions: Optional[List[GroupPermission]] = None) -> Dict[str, Any]:
        """组装用户组返回结构，保持API返回稳定"""
        group_dict = self._to_dict(group)
        if permissions is None:
            permissions = list(group.permissions or [])
        group_dict["permissions"] = [
            {
                "category": item.category,
                "enabled": bool(item.enabled),
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in permissions
        ]
        return group_dict

    def _ensure_group_permission_rows(self, session: DBSession, group_id: str):
        """确保用户组具备全量权限类别行"""
        existing = session.query(GroupPermission).filter(GroupPermission.group_id == group_id).all()
        existing_categories = {item.category for item in existing}
        for category in self.PERMISSION_CATEGORIES:
            if category in existing_categories:
                continue
            session.add(GroupPermission(group_id=group_id, category=category, enabled=False))

    def _ensure_system_groups(self, session: DBSession):
        """确保系统预置用户组与权限存在"""
        existing_groups = session.query(UserGroup).all()
        group_by_code = {group.code: group for group in existing_groups}
        for definition in self.SYSTEM_GROUP_DEFINITIONS:
            group = group_by_code.get(definition["code"])
            if not group:
                group = UserGroup(
                    code=definition["code"],
                    name=definition["name"],
                    description=definition["description"],
                    is_system=bool(definition["is_system"]),
                )
                session.add(group)
                session.flush()
            else:
                group.name = definition["name"]
                group.description = definition["description"]
                group.is_system = bool(definition["is_system"])
            self._ensure_group_permission_rows(session, str(group.id))
            permission_by_category = {
                item.category: item
                for item in session.query(GroupPermission).filter(GroupPermission.group_id == group.id).all()
            }
            for category, enabled in definition["categories"].items():
                permission_row = permission_by_category.get(category)
                if permission_row:
                    permission_row.enabled = bool(enabled)

    def _sync_user_default_group(self, session: DBSession, user_id: str, role: str):
        """按角色将用户映射到默认系统组，避免新用户无组"""
        target_code = self.ROLE_TO_SYSTEM_GROUP_CODE.get((role or "viewer").lower(), "viewer_group")
        group = session.query(UserGroup).filter(UserGroup.code == target_code).first()
        if not group:
            return
        exists = session.query(UserGroupMember).filter(
            UserGroupMember.user_id == user_id,
            UserGroupMember.group_id == group.id
        ).first()
        if not exists:
            session.add(UserGroupMember(user_id=user_id, group_id=group.id))

    def _ensure_default_super_admin(self, session: DBSession):
        """确保默认登录账户在数据库中具备超级管理员能力。"""
        default_username = (WEB_USERNAME() or "admin").strip() or "admin"
        default_password = WEB_PASSWORD() or "admin123"

        existing_default_user = session.query(User).filter(User.username == default_username).first()
        if existing_default_user:
            if (existing_default_user.role or "").lower() != "super_admin":
                existing_default_user.role = "super_admin"
            if not bool(existing_default_user.is_active):
                existing_default_user.is_active = True
            self._sync_user_default_group(session, str(existing_default_user.id), "super_admin")
            return

        has_any_user = session.query(User.id).first()
        if has_any_user:
            return

        created_user = User(
            username=default_username,
            password_hash=hash_password(default_password),
            role="super_admin",
            is_active=True,
        )
        session.add(created_user)
        session.flush()
        self._sync_user_default_group(session, str(created_user.id), "super_admin")
        self._bootstrap_user_base_assets(session, str(created_user.id))

    def _iter_system_ai_criteria_templates(self) -> List[Dict[str, str]]:
        """扫描系统级 AI 标准模板（requirement/ 与 criteria/）。"""
        template_sources = (
            ("requirement", self.project_root / "requirement"),
            ("criteria", self.project_root / "criteria"),
        )
        templates: List[Dict[str, str]] = []

        for source, directory in template_sources:
            if not directory.exists():
                continue
            for file_path in sorted(directory.glob("*.txt")):
                try:
                    content = file_path.read_text(encoding="utf-8").strip()
                except Exception:
                    continue
                if not content:
                    continue
                templates.append(
                    {
                        "source": source,
                        "name": file_path.stem,
                        "content": content,
                    }
                )

        return templates

    def _ensure_system_ai_criteria(self, session: DBSession):
        """确保系统级 AI 标准存在，为新用户初始化提供基线资源。"""
        existing_system = session.query(AiCriteria).filter(AiCriteria.owner_id == None).all()
        existing_by_name = {item.name: item for item in existing_system}

        for template in self._iter_system_ai_criteria_templates():
            template_name = (template.get("name") or "").strip()
            if not template_name or template_name in existing_by_name:
                continue
            new_criteria = AiCriteria(
                owner_id=None,
                name=template_name,
                content=template.get("content") or "",
                is_default=True,
            )
            session.add(new_criteria)
            session.flush()
            existing_by_name[template_name] = new_criteria

    def _bootstrap_user_base_assets(self, session: DBSession, user_id: str):
        """为新用户补齐系统级基础资源，保证开箱可用。"""
        self._ensure_system_ai_criteria(session)

        system_criteria = session.query(AiCriteria).filter(AiCriteria.owner_id == None).all()
        user_criteria_names = {
            item.name
            for item in session.query(AiCriteria).filter(AiCriteria.owner_id == user_id).all()
            if item.name
        }
        for system_item in system_criteria:
            if system_item.name in user_criteria_names:
                continue
            copied_criteria = AiCriteria(
                owner_id=user_id,
                name=system_item.name,
                content=system_item.content,
                is_default=bool(system_item.is_default),
            )
            session.add(copied_criteria)

        system_profiles = session.query(BayesProfile).filter(BayesProfile.owner_id == None).all()
        if not system_profiles:
            return

        user_profiles = session.query(BayesProfile).filter(BayesProfile.owner_id == user_id).all()
        user_profile_by_version = {profile.version: profile for profile in user_profiles}

        for system_profile in system_profiles:
            if system_profile.version in user_profile_by_version:
                continue
            copied_profile = BayesProfile(
                owner_id=user_id,
                version=system_profile.version,
                display_name=system_profile.display_name,
                recommendation_fusion=system_profile.recommendation_fusion,
                bayes_feature_rules=system_profile.bayes_feature_rules,
                is_default=bool(system_profile.is_default),
            )
            session.add(copied_profile)
            session.flush()
            user_profile_by_version[copied_profile.version] = copied_profile

        system_samples = session.query(BayesSample).filter(BayesSample.owner_id == None).all()
        if not system_samples:
            return

        samples_by_version: Dict[str, List[BayesSample]] = {}
        for sample in system_samples:
            samples_by_version.setdefault(sample.profile_version, []).append(sample)

        for profile_version, user_profile in user_profile_by_version.items():
            has_user_samples = session.query(BayesSample.id).filter(
                BayesSample.owner_id == user_id,
                BayesSample.profile_version == profile_version
            ).first()
            if has_user_samples:
                continue

            for sample in samples_by_version.get(profile_version, []):
                copied_sample = BayesSample(
                    owner_id=user_id,
                    profile_id=user_profile.id if user_profile else None,
                    profile_version=sample.profile_version,
                    name=sample.name,
                    vector=list(sample.vector or []),
                    label=sample.label,
                    source=sample.source or "preset",
                    item_id=sample.item_id,
                    note=sample.note,
                )
                session.add(copied_sample)
    
    # ============== 用户管理 ==============
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取用户"""
        with self.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            return self._to_dict(user, exclude=['password_hash'])
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户"""
        with self.get_session() as session:
            user = session.query(User).filter(User.username == username).first()
            if user:
                result = self._to_dict(user)
                result['password_hash'] = user.password_hash  # 保留用于验证
                return result
            return None
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新用户"""
        with self.get_session() as session:
            self._ensure_system_groups(session)
            # 密码加密
            if 'password' in user_data:
                user_data['password_hash'] = hash_password(user_data.pop('password'))
            
            user = User(**user_data)
            session.add(user)
            session.flush()
            self._sync_user_default_group(session, str(user.id), user.role)
            self._bootstrap_user_base_assets(session, str(user.id))
            return self._to_dict(user, exclude=['password_hash'])
    
    def update_user(self, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新用户信息"""
        with self.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            
            # 密码加密
            if 'password' in updates:
                updates['password_hash'] = hash_password(updates.pop('password'))
            
            for key, value in updates.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            session.flush()
            return self._to_dict(user, exclude=['password_hash'])
    
    def list_users(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """获取用户列表"""
        with self.get_session() as session:
            users = session.query(User).offset(skip).limit(limit).all()
            return [self._to_dict(u, exclude=['password_hash']) for u in users]
    
    def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        with self.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                session.delete(user)
                return True
            return False

    # ============== 用户组管理 ==============

    def create_user_group(self, group_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建用户组"""
        with self.get_session() as session:
            self._ensure_system_groups(session)
            code = (group_data.get("code") or "").strip().lower()
            name = (group_data.get("name") or "").strip()
            if not code or not name:
                raise ValueError("用户组 code 和 name 不能为空")

            exists = session.query(UserGroup).filter(UserGroup.code == code).first()
            if exists:
                raise ValueError(f"用户组标识 {code} 已存在")

            group = UserGroup(
                code=code,
                name=name,
                description=group_data.get("description"),
                is_system=bool(group_data.get("is_system", False)),
                created_by=group_data.get("created_by"),
            )
            session.add(group)
            session.flush()
            self._ensure_group_permission_rows(session, str(group.id))
            permission_data = group_data.get("permissions")
            if isinstance(permission_data, dict):
                permission_rows = session.query(GroupPermission).filter(GroupPermission.group_id == group.id).all()
                permission_map = {item.category: item for item in permission_rows}
                for category in self.PERMISSION_CATEGORIES:
                    if category not in permission_data:
                        continue
                    row = permission_map.get(category)
                    if row:
                        row.enabled = bool(permission_data.get(category))
            permissions = session.query(GroupPermission).filter(GroupPermission.group_id == group.id).all()
            return self._build_group_payload(group, permissions)

    def get_user_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取用户组"""
        with self.get_session() as session:
            group = session.query(UserGroup).filter(UserGroup.id == group_id).first()
            if not group:
                return None
            self._ensure_group_permission_rows(session, str(group.id))
            permissions = session.query(GroupPermission).filter(GroupPermission.group_id == group.id).all()
            return self._build_group_payload(group, permissions)

    def list_user_groups(self) -> List[Dict[str, Any]]:
        """获取用户组列表"""
        with self.get_session() as session:
            self._ensure_system_groups(session)
            groups = session.query(UserGroup).order_by(UserGroup.is_system.desc(), UserGroup.created_at.asc()).all()
            all_permissions = session.query(GroupPermission).all()
            permission_map: Dict[str, List[GroupPermission]] = {}
            for permission in all_permissions:
                key = str(permission.group_id)
                permission_map.setdefault(key, []).append(permission)
            result = []
            for group in groups:
                group_key = str(group.id)
                payload = self._build_group_payload(group, permission_map.get(group_key, []))
                member_count = session.query(UserGroupMember).filter(UserGroupMember.group_id == group.id).count()
                payload["member_count"] = member_count
                result.append(payload)
            return result

    def update_user_group(self, group_id: str, group_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新用户组"""
        with self.get_session() as session:
            group = session.query(UserGroup).filter(UserGroup.id == group_id).first()
            if not group:
                return None

            if "code" in group_data:
                new_code = (group_data.get("code") or "").strip().lower()
                if not new_code:
                    raise ValueError("用户组 code 不能为空")
                exists = session.query(UserGroup).filter(
                    UserGroup.code == new_code,
                    UserGroup.id != group.id
                ).first()
                if exists:
                    raise ValueError(f"用户组标识 {new_code} 已存在")
                group.code = new_code

            if "name" in group_data:
                new_name = (group_data.get("name") or "").strip()
                if not new_name:
                    raise ValueError("用户组名称不能为空")
                group.name = new_name

            if "description" in group_data:
                group.description = group_data.get("description")

            if "permissions" in group_data and isinstance(group_data["permissions"], dict):
                self._ensure_group_permission_rows(session, str(group.id))
                permission_rows = session.query(GroupPermission).filter(GroupPermission.group_id == group.id).all()
                permission_map = {item.category: item for item in permission_rows}
                for category, enabled in group_data["permissions"].items():
                    if category not in self.PERMISSION_CATEGORIES:
                        continue
                    row = permission_map.get(category)
                    if row:
                        row.enabled = bool(enabled)

            session.flush()
            permissions = session.query(GroupPermission).filter(GroupPermission.group_id == group.id).all()
            return self._build_group_payload(group, permissions)

    def delete_user_group(self, group_id: str) -> bool:
        """删除用户组"""
        with self.get_session() as session:
            group = session.query(UserGroup).filter(UserGroup.id == group_id).first()
            if not group:
                return False
            if group.is_system:
                raise ValueError("系统预置组不可删除")
            session.delete(group)
            return True

    def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户所属用户组"""
        with self.get_session() as session:
            self._ensure_system_groups(session)
            rows = session.query(UserGroupMember).filter(UserGroupMember.user_id == user_id).all()
            if not rows:
                # 兼容历史数据：首次读取时为老用户补齐默认系统组，便于切换到用户组单体系
                user = session.query(User).filter(User.id == user_id).first()
                if user:
                    self._sync_user_default_group(session, str(user.id), user.role)
                    session.flush()
                    rows = session.query(UserGroupMember).filter(UserGroupMember.user_id == user_id).all()
            group_ids = [row.group_id for row in rows]
            if not group_ids:
                return []
            groups = session.query(UserGroup).filter(UserGroup.id.in_(group_ids)).all()
            permissions = session.query(GroupPermission).filter(GroupPermission.group_id.in_(group_ids)).all()
            permission_map: Dict[str, List[GroupPermission]] = {}
            for permission in permissions:
                permission_map.setdefault(str(permission.group_id), []).append(permission)
            return [
                self._build_group_payload(group, permission_map.get(str(group.id), []))
                for group in groups
            ]

    def set_user_groups(self, user_id: str, group_ids: List[str]) -> bool:
        """覆盖设置用户所属组"""
        with self.get_session() as session:
            self._ensure_system_groups(session)
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return False

            normalized_group_ids = [group_id for group_id in group_ids if group_id]
            if normalized_group_ids:
                existing_groups = session.query(UserGroup.id).filter(UserGroup.id.in_(normalized_group_ids)).all()
                existing_group_id_set = {str(item[0]) for item in existing_groups}
                unknown_group_ids = [group_id for group_id in normalized_group_ids if group_id not in existing_group_id_set]
                if unknown_group_ids:
                    raise ValueError(f"用户组不存在: {unknown_group_ids}")

            session.query(UserGroupMember).filter(UserGroupMember.user_id == user_id).delete()
            for group_id in normalized_group_ids:
                session.add(UserGroupMember(user_id=user_id, group_id=group_id))
            return True

    def get_group_permissions(self, group_id: str) -> List[Dict[str, Any]]:
        """获取用户组权限"""
        with self.get_session() as session:
            group = session.query(UserGroup).filter(UserGroup.id == group_id).first()
            if not group:
                return []
            self._ensure_group_permission_rows(session, group_id)
            permissions = session.query(GroupPermission).filter(GroupPermission.group_id == group_id).all()
            return [
                {
                    "category": row.category,
                    "enabled": bool(row.enabled),
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in permissions
            ]

    def set_group_permissions(self, group_id: str, categories: Dict[str, bool]) -> bool:
        """设置用户组权限"""
        with self.get_session() as session:
            group = session.query(UserGroup).filter(UserGroup.id == group_id).first()
            if not group:
                return False
            self._ensure_group_permission_rows(session, group_id)
            permission_rows = session.query(GroupPermission).filter(GroupPermission.group_id == group_id).all()
            permission_map = {item.category: item for item in permission_rows}
            for category in self.PERMISSION_CATEGORIES:
                if category not in categories:
                    continue
                row = permission_map.get(category)
                if row:
                    row.enabled = bool(categories.get(category))
            return True
    
    # ============== 会话管理 ==============
    
    def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建会话"""
        with self.get_session() as db_session:
            # 对 token 进行哈希
            if 'token' in session_data:
                session_data['token_hash'] = hash_token(session_data.pop('token'))
            
            session = Session(**session_data)
            db_session.add(session)
            db_session.flush()
            return self._to_dict(session)
    
    def get_session_by_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """根据token哈希获取会话"""
        with self.get_session() as db_session:
            session = db_session.query(Session).filter(
                Session.token_hash == token_hash,
                Session.expires_at > datetime.utcnow()
            ).first()
            return self._to_dict(session)
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        with self.get_session() as db_session:
            session = db_session.query(Session).filter(Session.id == session_id).first()
            if session:
                db_session.delete(session)
                return True
            return False
    
    def delete_user_sessions(self, user_id: str) -> int:
        """删除用户的所有会话"""
        with self.get_session() as db_session:
            count = db_session.query(Session).filter(Session.user_id == user_id).delete()
            return count
    
    # ============== 任务管理 ==============
    
    def get_tasks(self, owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取任务列表"""
        with self.get_session() as session:
            query = session.query(Task)
            if owner_id:
                query = query.filter(Task.owner_id == owner_id)
            tasks = query.order_by(Task.order).all()
            return [self._merge_task_filters(self._to_dict(t)) for t in tasks]
    
    def get_task_by_name(self, task_name: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """根据任务名获取任务"""
        with self.get_session() as session:
            query = session.query(Task).filter(Task.task_name == task_name)
            if owner_id:
                query = query.filter(Task.owner_id == owner_id)
            task = query.first()
            return self._merge_task_filters(self._to_dict(task))
    
    def save_task(self, task_data: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存任务"""
        with self.get_session() as session:
            task_data = self._split_task_payload(task_data)
            task_name = task_data.get('task_name')
            
            # 设置所有者
            if owner_id:
                task_data['owner_id'] = owner_id
            
            # 查找是否存在
            existing = session.query(Task).filter(
                Task.task_name == task_name,
                Task.owner_id == task_data.get('owner_id')
            ).first()
            
            if existing:
                if "filters" in task_data:
                    existing_filters = existing.filters if isinstance(existing.filters, dict) else {}
                    incoming_filters = task_data.get("filters")
                    if isinstance(incoming_filters, dict):
                        task_data["filters"] = {**existing_filters, **incoming_filters}
                for key, value in task_data.items():
                    if hasattr(existing, key) and key != 'id':
                        setattr(existing, key, value)
                session.flush()
                return self._merge_task_filters(self._to_dict(existing))
            else:
                # 设置order
                if 'order' not in task_data:
                    max_order = session.query(Task.order).filter(
                        Task.owner_id == task_data.get('owner_id')
                    ).order_by(Task.order.desc()).first()
                    task_data['order'] = (max_order[0] if max_order else 0) + 1
                
                task = Task(**task_data)
                session.add(task)
                session.flush()
                return self._merge_task_filters(self._to_dict(task))
    
    def delete_task(self, task_name: str, owner_id: Optional[str] = None) -> bool:
        """删除任务"""
        with self.get_session() as session:
            query = session.query(Task).filter(Task.task_name == task_name)
            if owner_id:
                query = query.filter(Task.owner_id == owner_id)
            count = query.delete()
            return count > 0
    
    def update_task_order(self, ordered_names: List[str], owner_id: Optional[str] = None) -> bool:
        """更新任务排序"""
        with self.get_session() as session:
            for i, name in enumerate(ordered_names):
                query = session.query(Task).filter(Task.task_name == name)
                if owner_id:
                    query = query.filter(Task.owner_id == owner_id)
                task = query.first()
                if task:
                    task.order = i + 1
            return True
    
    # ============== 监控结果管理 ==============
    
    def save_result(self, task_name: str, result_data: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存监控结果"""
        with self.get_session() as session:
            # 获取任务ID
            task_query = session.query(Task).filter(Task.task_name == task_name)
            if owner_id:
                task_query = task_query.filter(Task.owner_id == owner_id)
            task = task_query.first()
            task_id = str(task.id) if task else None
            
            # 转换结果数据格式
            item_id = result_data.get("商品信息", {}).get("商品ID", "")
            ai_analysis = result_data.get("ai_analysis") or result_data.get("AI分析") or {}

            # 兼容新旧结构：优先使用显式字段，缺失时从 ai_analysis 推断推荐状态与推荐度
            recommended_levels = {"STRONG_BUY", "CAUTIOUS_BUY", "CONDITIONAL_BUY"}
            recommendation_level = str(ai_analysis.get("recommendation_level") or "").strip()
            if isinstance(result_data.get("is_recommended"), bool):
                is_recommended = bool(result_data.get("is_recommended"))
            elif recommendation_level:
                is_recommended = recommendation_level in recommended_levels
            else:
                is_recommended = bool(ai_analysis.get("is_recommended", False))

            recommendation_score = result_data.get("推荐度")
            if recommendation_score is None:
                score_v2 = ai_analysis.get("recommendation_score_v2") if isinstance(ai_analysis, dict) else None
                if isinstance(score_v2, dict):
                    raw_score = score_v2.get("recommendation_score")
                    if isinstance(raw_score, (int, float)):
                        recommendation_score = float(raw_score)
            
            result = MonitoringResult(
                owner_id=owner_id,
                task_id=task_id,
                item_id=item_id,
                product_info=result_data.get("商品信息"),
                seller_info=result_data.get("卖家信息"),
                ai_analysis=ai_analysis,
                ml_precalc=result_data.get("ml_precalc"),
                recommendation_score=recommendation_score,
                is_recommended=is_recommended
            )
            
            session.add(result)
            session.flush()
            return self._to_dict(result)
    
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
        with self.get_session() as session:
            # 获取任务ID
            task_query = session.query(Task).filter(Task.task_name == task_name)
            if owner_id:
                task_query = task_query.filter(Task.owner_id == owner_id)
            task = task_query.first()
            if not task:
                return []
            
            query = session.query(MonitoringResult).filter(MonitoringResult.task_id == task.id)
            
            if owner_id:
                query = query.filter(MonitoringResult.owner_id == owner_id)
            
            if recommended_only:
                query = query.filter(MonitoringResult.is_recommended == True)
            
            # 关键词筛选 (JSONB查询)
            if keyword:
                query = query.filter(
                    MonitoringResult.product_info['商品标题'].astext.ilike(f'%{keyword}%')
                )
            
            results = query.order_by(MonitoringResult.crawled_at.desc()).offset(offset).limit(limit).all()
            return [self._result_to_legacy_format(r) for r in results]
    
    def _result_to_legacy_format(self, result: MonitoringResult) -> Dict[str, Any]:
        """将结果转换为旧格式（保持兼容性）"""
        return {
            "商品信息": result.product_info or {},
            "卖家信息": result.seller_info or {},
            "AI分析": result.ai_analysis or {},
            "ml_precalc": result.ml_precalc or {},
            "推荐度": result.recommendation_score,
            "is_recommended": result.is_recommended,
            "crawled_at": result.crawled_at.isoformat() if result.crawled_at else None
        }
    
    def get_result_by_item_id(self, item_id: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """根据商品ID获取结果"""
        with self.get_session() as session:
            query = session.query(MonitoringResult).filter(MonitoringResult.item_id == item_id)
            if owner_id:
                query = query.filter(MonitoringResult.owner_id == owner_id)
            result = query.first()
            return self._result_to_legacy_format(result) if result else None
    
    def delete_results(
        self, 
        task_name: str, 
        owner_id: Optional[str] = None,
        item_ids: Optional[List[str]] = None
    ) -> int:
        """删除监控结果"""
        with self.get_session() as session:
            # 获取任务ID
            task_query = session.query(Task).filter(Task.task_name == task_name)
            if owner_id:
                task_query = task_query.filter(Task.owner_id == owner_id)
            task = task_query.first()
            if not task:
                return 0
            
            query = session.query(MonitoringResult).filter(MonitoringResult.task_id == task.id)
            
            if owner_id:
                query = query.filter(MonitoringResult.owner_id == owner_id)
            
            if item_ids:
                query = query.filter(MonitoringResult.item_id.in_(item_ids))
            
            count = query.delete(synchronize_session=False)
            return count
    
    # ============== 贝叶斯配置管理 ==============
    
    def get_bayes_profile(self, version: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取贝叶斯配置"""
        with self.get_session() as session:
            query = session.query(BayesProfile).filter(BayesProfile.version == version)
            
            # 优先获取用户自己的配置，否则获取系统配置
            if owner_id:
                user_profile = query.filter(BayesProfile.owner_id == owner_id).first()
                if user_profile:
                    return self._to_dict(user_profile)
            
            # 获取系统配置
            system_profile = query.filter(BayesProfile.owner_id == None).first()
            return self._to_dict(system_profile)
    
    def save_bayes_profile(self, profile_data: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存贝叶斯配置"""
        with self.get_session() as session:
            version = profile_data.get('version', 'bayes_v1')
            
            if owner_id:
                profile_data['owner_id'] = owner_id
            
            existing = session.query(BayesProfile).filter(
                BayesProfile.version == version,
                BayesProfile.owner_id == profile_data.get('owner_id')
            ).first()
            
            if existing:
                for key, value in profile_data.items():
                    if hasattr(existing, key) and key != 'id':
                        setattr(existing, key, value)
                session.flush()
                return self._to_dict(existing)
            else:
                profile = BayesProfile(**profile_data)
                session.add(profile)
                session.flush()
                return self._to_dict(profile)
    
    def list_bayes_profiles(self, owner_id: Optional[str] = None, include_system: bool = True) -> List[Dict[str, Any]]:
        """获取贝叶斯配置列表"""
        with self.get_session() as session:
            conditions = []
            
            if owner_id:
                conditions.append(BayesProfile.owner_id == owner_id)
            
            if include_system:
                conditions.append(BayesProfile.owner_id == None)
            
            if conditions:
                query = session.query(BayesProfile).filter(or_(*conditions))
            else:
                query = session.query(BayesProfile)
            
            profiles = query.all()
            return [self._to_dict(p) for p in profiles]
    
    # ============== 贝叶斯样本管理 ==============
    
    def get_bayes_samples(
        self, 
        profile_version: str, 
        owner_id: Optional[str] = None,
        label: Optional[int] = None,
        include_system: bool = True
    ) -> List[Dict[str, Any]]:
        """获取贝叶斯样本"""
        with self.get_session() as session:
            conditions = [BayesSample.profile_version == profile_version]
            
            owner_conditions = []
            if owner_id:
                owner_conditions.append(BayesSample.owner_id == owner_id)
            if include_system:
                owner_conditions.append(BayesSample.owner_id == None)
            
            if owner_conditions:
                conditions.append(or_(*owner_conditions))
            
            if label is not None:
                conditions.append(BayesSample.label == label)
            
            samples = session.query(BayesSample).filter(and_(*conditions)).all()
            return [self._to_dict(s) for s in samples]
    
    def add_bayes_sample(self, sample_data: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """添加贝叶斯样本"""
        with self.get_session() as session:
            if owner_id:
                sample_data['owner_id'] = owner_id
            
            sample = BayesSample(**sample_data)
            session.add(sample)
            session.flush()
            return self._to_dict(sample)
    
    def delete_bayes_sample(self, sample_id: str, owner_id: Optional[str] = None) -> bool:
        """删除贝叶斯样本"""
        with self.get_session() as session:
            query = session.query(BayesSample).filter(BayesSample.id == sample_id)
            if owner_id:
                query = query.filter(BayesSample.owner_id == owner_id)
            count = query.delete()
            return count > 0
    
    # ============== 用户反馈管理 ==============
    
    def save_feedback(
        self, 
        user_id: str,
        result_id: str, 
        feedback_type: str, 
        feature_vector: List[float]
    ) -> Dict[str, Any]:
        """保存用户反馈"""
        if not user_id:
            raise ValueError("user_id 不能为空")

        try:
            user_uuid = UUID(str(user_id))
        except (TypeError, ValueError) as e:
            raise ValueError("user_id 格式无效") from e

        with self.get_session() as session:
            resolved_result = None

            # 优先按主键ID匹配，兼容直接传入 monitoring_results.id 的场景
            try:
                result_uuid = UUID(str(result_id))
                resolved_result = session.query(MonitoringResult).filter(
                    MonitoringResult.id == result_uuid,
                    MonitoringResult.owner_id == user_uuid
                ).first()
            except (TypeError, ValueError):
                resolved_result = None

            # 回退按 item_id 匹配，兼容前端传入商品ID的场景
            if not resolved_result:
                resolved_result = session.query(MonitoringResult).filter(
                    MonitoringResult.item_id == str(result_id),
                    MonitoringResult.owner_id == user_uuid
                ).first()

            if not resolved_result:
                raise ValueError("未找到当前用户可访问的结果记录，无法保存反馈")

            feedback = UserFeedback(
                user_id=user_uuid,
                result_id=resolved_result.id,
                feedback_type=feedback_type,
                feature_vector=feature_vector
            )
            session.add(feedback)
            session.flush()
            return self._to_dict(feedback)
    
    def get_feedbacks(
        self, 
        user_id: Optional[str] = None,
        result_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取用户反馈列表"""
        with self.get_session() as session:
            query = session.query(UserFeedback)
            
            if user_id:
                query = query.filter(UserFeedback.user_id == user_id)
            if result_id:
                query = query.filter(UserFeedback.result_id == result_id)
            
            feedbacks = query.order_by(UserFeedback.created_at.desc()).limit(limit).all()
            return [self._to_dict(f) for f in feedbacks]
    
    def delete_feedback(
        self,
        user_id: str,
        result_id: str
    ) -> bool:
        """删除指定结果的用户反馈及关联贝叶斯样本"""
        if not user_id:
            raise ValueError("user_id 不能为空")
        try:
            user_uuid = UUID(str(user_id))
        except (TypeError, ValueError) as e:
            raise ValueError("user_id 格式无效") from e

        with self.get_session() as session:
            resolved_result = None
            try:
                result_uuid = UUID(str(result_id))
                resolved_result = session.query(MonitoringResult).filter(
                    MonitoringResult.id == result_uuid,
                    MonitoringResult.owner_id == user_uuid
                ).first()
            except (TypeError, ValueError):
                resolved_result = None

            if not resolved_result:
                resolved_result = session.query(MonitoringResult).filter(
                    MonitoringResult.item_id == str(result_id),
                    MonitoringResult.owner_id == user_uuid
                ).first()

            if not resolved_result:
                return False

            deleted = session.query(UserFeedback).filter(
                UserFeedback.user_id == user_uuid,
                UserFeedback.result_id == resolved_result.id
            ).delete(synchronize_session=False)

            session.query(BayesSample).filter(
                BayesSample.item_id == str(result_id),
                BayesSample.source == 'user',
                BayesSample.owner_id == user_uuid
            ).delete(synchronize_session=False)

            return deleted > 0
    
    # ============== AI标准管理 ==============
    
    def get_ai_criteria(self, criteria_id: str) -> Optional[Dict[str, Any]]:
        """获取AI标准"""
        with self.get_session() as session:
            criteria = session.query(AiCriteria).filter(AiCriteria.id == criteria_id).first()
            return self._to_dict(criteria)
    
    def list_ai_criteria(self, owner_id: Optional[str] = None, include_system: bool = True) -> List[Dict[str, Any]]:
        """获取AI标准列表"""
        with self.get_session() as session:
            conditions = []
            
            if owner_id:
                conditions.append(AiCriteria.owner_id == owner_id)
            if include_system:
                conditions.append(AiCriteria.owner_id == None)
            
            if conditions:
                query = session.query(AiCriteria).filter(or_(*conditions))
            else:
                query = session.query(AiCriteria)
            
            criteria_list = query.all()
            return [self._to_dict(c) for c in criteria_list]
    
    def save_ai_criteria(self, criteria_data: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存AI标准"""
        with self.get_session() as session:
            if owner_id:
                criteria_data['owner_id'] = owner_id
            
            criteria_id = criteria_data.get('id')
            if criteria_id:
                existing = session.query(AiCriteria).filter(AiCriteria.id == criteria_id).first()
                if existing:
                    for key, value in criteria_data.items():
                        if hasattr(existing, key) and key != 'id':
                            setattr(existing, key, value)
                    session.flush()
                    config_dict = self._to_dict(existing)
                    if config_dict.get('config_encrypted'):
                        import json
                        config_dict['config'] = json.loads(
                            decrypt_sensitive(str(user_id), config_dict['config_encrypted'])
                        )
                        del config_dict['config_encrypted']
                    return config_dict
            
            criteria = AiCriteria(**{k: v for k, v in criteria_data.items() if k != 'id'})
            session.add(criteria)
            session.flush()
            return self._to_dict(criteria)
    
    def delete_ai_criteria(self, criteria_id: str, owner_id: Optional[str] = None) -> bool:
        """删除AI标准"""
        with self.get_session() as session:
            query = session.query(AiCriteria).filter(AiCriteria.id == criteria_id)
            if owner_id:
                query = query.filter(AiCriteria.owner_id == owner_id)
            count = query.delete()
            return count > 0
    
    # ============== 用户API配置管理 ==============
    
    def get_user_api_configs(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的API配置列表"""
        with self.get_session() as session:
            configs = session.query(UserApiConfig).filter(UserApiConfig.user_id == user_id).all()
            result = []
            for c in configs:
                config_dict = self._to_dict(c)
                # 解密API密钥
                if config_dict.get('api_key_encrypted'):
                    try:
                        config_dict['api_key'] = decrypt_sensitive(str(user_id), config_dict['api_key_encrypted'])
                        del config_dict['api_key_encrypted']
                    except Exception:
                        config_dict['api_key'] = ""
                        config_dict['api_key_invalid'] = True
                result.append(config_dict)
            return result
    
    def save_user_api_config(self, user_id: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """保存用户API配置"""
        with self.get_session() as session:
            config_data['user_id'] = user_id
            
            # 加密API密钥
            if 'api_key' in config_data:
                config_data['api_key_encrypted'] = encrypt_sensitive(str(user_id), config_data.pop('api_key'))
            
            config_id = config_data.get('id')
            if config_id:
                existing = session.query(UserApiConfig).filter(
                    UserApiConfig.id == config_id,
                    UserApiConfig.user_id == user_id
                ).first()
                if existing:
                    for key, value in config_data.items():
                        if hasattr(existing, key) and key != 'id':
                            setattr(existing, key, value)
                    session.flush()
                    return self._to_dict(existing)
            
            config = UserApiConfig(**{k: v for k, v in config_data.items() if k != 'id'})
            session.add(config)
            session.flush()
            config_dict = self._to_dict(config)
            if config_dict.get('api_key_encrypted'):
                try:
                    config_dict['api_key'] = decrypt_sensitive(str(user_id), config_dict['api_key_encrypted'])
                    del config_dict['api_key_encrypted']
                except Exception:
                    config_dict['api_key'] = ""
                    config_dict['api_key_invalid'] = True
            return config_dict
    
    def delete_user_api_config(self, config_id: str, user_id: str) -> bool:
        """删除用户API配置"""
        with self.get_session() as session:
            count = session.query(UserApiConfig).filter(
                UserApiConfig.id == config_id,
                UserApiConfig.user_id == user_id
            ).delete()
            return count > 0
    
    def get_default_api_config(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户默认API配置"""
        with self.get_session() as session:
            # 首先查找用户的默认配置
            config = session.query(UserApiConfig).filter(
                UserApiConfig.user_id == user_id,
                UserApiConfig.is_default == True
            ).first()
            
            if config:
                config_dict = self._to_dict(config)
                if config_dict.get('api_key_encrypted'):
                    try:
                        config_dict['api_key'] = decrypt_sensitive(str(user_id), config_dict['api_key_encrypted'])
                        del config_dict['api_key_encrypted']
                    except Exception:
                        config_dict['api_key'] = ""
                        config_dict['api_key_invalid'] = True
                return config_dict
            
            # 如果没有，返回用户的第一个配置
            config = session.query(UserApiConfig).filter(UserApiConfig.user_id == user_id).first()
            if config:
                config_dict = self._to_dict(config)
                if config_dict.get('api_key_encrypted'):
                    try:
                        config_dict['api_key'] = decrypt_sensitive(str(user_id), config_dict['api_key_encrypted'])
                        del config_dict['api_key_encrypted']
                    except Exception:
                        config_dict['api_key'] = ""
                        config_dict['api_key_invalid'] = True
                return config_dict
            
            return None
    
    # ============== 用户通知配置管理 ==============
    
    def get_user_notification_configs(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的通知配置列表"""
        with self.get_session() as session:
            configs = session.query(UserNotificationConfig).filter(
                UserNotificationConfig.user_id == user_id
            ).all()
            result = []
            for c in configs:
                config_dict = self._to_dict(c)
                # 解密配置
                if config_dict.get('config_encrypted'):
                    import json
                    config_dict['config'] = json.loads(
                        decrypt_sensitive(str(user_id), config_dict['config_encrypted'])
                    )
                    del config_dict['config_encrypted']
                result.append(config_dict)
            return result
    
    def save_user_notification_config(self, user_id: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """保存用户通知配置"""
        with self.get_session() as session:
            config_data['user_id'] = user_id
            
            # 加密配置
            if 'config' in config_data:
                import json
                config_data['config_encrypted'] = encrypt_sensitive(
                    str(user_id), 
                    json.dumps(config_data.pop('config'))
                )
            
            config_id = config_data.get('id')
            if config_id:
                existing = session.query(UserNotificationConfig).filter(
                    UserNotificationConfig.id == config_id,
                    UserNotificationConfig.user_id == user_id
                ).first()
                if existing:
                    for key, value in config_data.items():
                        if hasattr(existing, key) and key != 'id':
                            setattr(existing, key, value)
                    session.flush()
                    config_dict = self._to_dict(existing)
                    if config_dict.get('config_encrypted'):
                        import json
                        config_dict['config'] = json.loads(
                            decrypt_sensitive(str(user_id), config_dict['config_encrypted'])
                        )
                        del config_dict['config_encrypted']
                    return config_dict
            
            config = UserNotificationConfig(**{k: v for k, v in config_data.items() if k != 'id'})
            session.add(config)
            session.flush()
            config_dict = self._to_dict(config)
            if config_dict.get('config_encrypted'):
                import json
                config_dict['config'] = json.loads(
                    decrypt_sensitive(str(user_id), config_dict['config_encrypted'])
                )
                del config_dict['config_encrypted']
            return config_dict
    
    def delete_user_notification_config(self, config_id: str, user_id: str) -> bool:
        """删除用户通知配置"""
        with self.get_session() as session:
            count = session.query(UserNotificationConfig).filter(
                UserNotificationConfig.id == config_id,
                UserNotificationConfig.user_id == user_id
            ).delete()
            return count > 0
    
    # ============== 用户平台账号管理 ==============
    
    def get_user_platform_accounts(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的平台账号列表"""
        with self.get_session() as session:
            accounts = session.query(UserPlatformAccount).filter(
                UserPlatformAccount.user_id == user_id
            ).all()
            result = []
            for a in accounts:
                account_dict = self._to_dict(a)
                # 解密Cookie
                if account_dict.get('cookies_encrypted'):
                    account_dict['cookies'] = decrypt_sensitive(str(user_id), account_dict['cookies_encrypted'])
                    del account_dict['cookies_encrypted']
                result.append(account_dict)
            return result
    
    def save_user_platform_account(self, user_id: str, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """保存用户平台账号"""
        with self.get_session() as session:
            account_data['user_id'] = user_id
            
            # 加密Cookie
            if 'cookies' in account_data:
                account_data['cookies_encrypted'] = encrypt_sensitive(str(user_id), account_data.pop('cookies'))
            
            account_id = account_data.get('id')
            if account_id:
                existing = session.query(UserPlatformAccount).filter(
                    UserPlatformAccount.id == account_id,
                    UserPlatformAccount.user_id == user_id
                ).first()
                if existing:
                    for key, value in account_data.items():
                        if hasattr(existing, key) and key != 'id':
                            setattr(existing, key, value)
                    session.flush()
                    return self._to_dict(existing)
            
            account = UserPlatformAccount(**{k: v for k, v in account_data.items() if k != 'id'})
            session.add(account)
            session.flush()
            return self._to_dict(account)
    
    def delete_user_platform_account(self, account_id: str, user_id: str) -> bool:
        """删除用户平台账号"""
        with self.get_session() as session:
            count = session.query(UserPlatformAccount).filter(
                UserPlatformAccount.id == account_id,
                UserPlatformAccount.user_id == user_id
            ).delete()
            return count > 0
    
    def update_platform_account_cookies(self, account_id: str, user_id: str, cookies: str) -> bool:
        """更新平台账号Cookie"""
        with self.get_session() as session:
            account = session.query(UserPlatformAccount).filter(
                UserPlatformAccount.id == account_id,
                UserPlatformAccount.user_id == user_id
            ).first()
            
            if account:
                account.cookies_encrypted = encrypt_sensitive(str(user_id), cookies)
                account.last_used_at = datetime.utcnow()
                return True
            return False
    
    # ============== 审计日志 ==============
    
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
        with self.get_session() as session:
            log = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address
            )
            session.add(log)
            session.flush()
            return self._to_dict(log)
    
    def get_audit_logs(
        self, 
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取审计日志"""
        with self.get_session() as session:
            query = session.query(AuditLog)
            
            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            if action:
                query = query.filter(AuditLog.action == action)
            if resource_type:
                query = query.filter(AuditLog.resource_type == resource_type)
            
            logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
            return [self._to_dict(l) for l in logs]
