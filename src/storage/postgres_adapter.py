"""
PostgreSQL Storage Adapter - PostgreSQL 数据库存储适配器

实现 StorageInterface，使用 SQLAlchemy ORM 操作 PostgreSQL 数据库。
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, and_, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker, Session as DBSession

from .interface import StorageInterface
from .models import (
    Base, User, Session, Task, MonitoringResult,
    BayesProfile, BayesSample, UserFeedback, AiCriteria, PromptTemplate,
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
    DEFAULT_BAYES_FEATURE_NAMES = [
        "seller_credit_level_score",
        "positive_rate_score",
        "register_score",
        "on_sale_score",
        "img_score",
        "desc_score",
        "heat_score",
        "category_score",
    ]
    
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
            self._ensure_system_prompt_templates(session)
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

    def _normalize_prompt_template_name(self, name: str) -> str:
        """标准化 Prompt 模板名称。"""
        normalized = str(name or "").strip()
        if not normalized:
            raise ValueError("Prompt 模板名称不能为空")
        if not normalized.lower().endswith(".txt"):
            normalized = f"{normalized}.txt"
        return normalized

    def _iter_system_prompt_templates(self) -> List[Dict[str, str]]:
        """扫描系统级 Prompt 模板（prompts/*.txt）。"""
        prompt_dir = self.project_root / "prompts"
        templates: List[Dict[str, str]] = []
        if not prompt_dir.exists():
            return templates

        for file_path in sorted(prompt_dir.glob("*.txt")):
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue
            templates.append(
                {
                    "name": file_path.name,
                    "content": content,
                    "is_default": file_path.name == "base_prompt.txt",
                }
            )
        return templates

    def _ensure_system_prompt_templates(self, session: DBSession):
        """确保系统级 Prompt 模板存在。"""
        existing_templates = session.query(PromptTemplate).filter(PromptTemplate.owner_id == None).all()
        existing_names = {item.name for item in existing_templates if item.name}

        for template in self._iter_system_prompt_templates():
            template_name = self._normalize_prompt_template_name(template.get("name"))
            if template_name in existing_names:
                continue
            session.add(
                PromptTemplate(
                    owner_id=None,
                    name=template_name,
                    content=str(template.get("content") or ""),
                    is_default=bool(template.get("is_default")),
                )
            )
            existing_names.add(template_name)

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

    def _get_task_by_name(self, session: DBSession, task_name: str, owner_id: Optional[str]) -> Optional[Task]:
        """按任务名获取任务对象。"""
        task_query = session.query(Task).filter(Task.task_name == task_name)
        if owner_id:
            task_query = task_query.filter(Task.owner_id == owner_id)
        return task_query.first()

    def _extract_result_item_id(self, result_data: Dict[str, Any]) -> str:
        """提取并规范化结果去重键，缺失商品ID时回退链接哈希。"""
        product_info = result_data.get("商品信息") if isinstance(result_data, dict) else {}
        if not isinstance(product_info, dict):
            product_info = {}

        raw_item_id = product_info.get("商品ID")
        item_id = str(raw_item_id).strip() if raw_item_id is not None else ""
        if item_id:
            return item_id

        raw_link = product_info.get("商品链接")
        link = str(raw_link).strip() if raw_link is not None else ""
        if not link:
            return ""
        link_key = link.split('&', 1)[0]
        if not link_key:
            return ""
        return f"link:{hashlib.sha1(link_key.encode('utf-8')).hexdigest()}"

    def _build_result_payload(
        self,
        session: DBSession,
        task_name: str,
        result_data: Dict[str, Any],
        owner_id: Optional[str],
    ) -> Dict[str, Any]:
        """构造监控结果入库载荷。"""
        task = self._get_task_by_name(session, task_name, owner_id)
        task_id = task.id if task else None
        item_id = self._extract_result_item_id(result_data)

        ai_analysis = result_data.get("ai_analysis") or result_data.get("AI分析") or {}
        if not isinstance(ai_analysis, dict):
            ai_analysis = {}

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
            score_v2 = ai_analysis.get("recommendation_score_v2")
            if isinstance(score_v2, dict):
                raw_score = score_v2.get("recommendation_score")
                if isinstance(raw_score, (int, float)):
                    recommendation_score = float(raw_score)

        product_info = result_data.get("商品信息")
        if not isinstance(product_info, dict):
            product_info = {}
        else:
            product_info = dict(product_info)
        if item_id and not str(product_info.get("商品ID") or "").strip():
            product_info["商品ID"] = item_id

        seller_info = result_data.get("卖家信息")
        if not isinstance(seller_info, dict):
            seller_info = {}

        return {
            "owner_id": owner_id or None,
            "task_id": task_id,
            "item_id": item_id,
            "product_info": product_info,
            "seller_info": seller_info,
            "ai_analysis": ai_analysis,
            "ml_precalc": result_data.get("ml_precalc"),
            "recommendation_score": recommendation_score,
            "is_recommended": is_recommended,
        }
    
    def save_result(self, task_name: str, result_data: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存监控结果"""
        with self.get_session() as session:
            payload = self._build_result_payload(session, task_name, result_data, owner_id)
            if not payload.get("item_id"):
                legacy_payload = json.dumps(result_data or {}, ensure_ascii=False, sort_keys=True)
                payload["item_id"] = f"legacy:{hashlib.sha1(legacy_payload.encode('utf-8')).hexdigest()}"
                if isinstance(payload.get("product_info"), dict):
                    payload["product_info"]["商品ID"] = payload["item_id"]

            result = MonitoringResult(**payload)
            
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

    def result_exists(
        self,
        item_id: str,
        owner_id: Optional[str] = None,
        task_name: Optional[str] = None
    ) -> bool:
        """检查结果是否已存在。"""
        normalized_item_id = str(item_id or "").strip()
        if not normalized_item_id:
            return False

        with self.get_session() as session:
            query = session.query(MonitoringResult).filter(MonitoringResult.item_id == normalized_item_id)
            if owner_id:
                query = query.filter(MonitoringResult.owner_id == owner_id)
            else:
                query = query.filter(MonitoringResult.owner_id.is_(None))

            # 当前数据库唯一约束为(owner_id, item_id)，为保持软硬去重口径一致，
            # PostgreSQL 后端在未完成task维度迁移前始终按owner范围判重。

            return query.first() is not None

    def save_result_if_absent(
        self,
        task_name: str,
        result_data: Dict[str, Any],
        owner_id: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """幂等保存结果（基于数据库唯一约束）。"""
        with self.get_session() as session:
            payload = self._build_result_payload(session, task_name, result_data, owner_id)
            if not payload.get("item_id"):
                return None, False

            insert_stmt = (
                insert(MonitoringResult)
                .values(**payload)
                .on_conflict_do_nothing(index_elements=["owner_id", "item_id"])
                .returning(MonitoringResult.id)
            )
            inserted_id = session.execute(insert_stmt).scalar_one_or_none()
            if inserted_id is None:
                return None, False

            created = session.query(MonitoringResult).filter(MonitoringResult.id == inserted_id).first()
            if not created:
                return None, False
            return self._result_to_legacy_format(created), True
    
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
    
    def _find_effective_bayes_profile(
        self,
        session: DBSession,
        version: str,
        owner_id: Optional[str] = None
    ) -> Optional[BayesProfile]:
        """查询生效的贝叶斯配置（用户优先，系统回退）。"""
        query = session.query(BayesProfile).filter(BayesProfile.version == version)
        if owner_id:
            user_profile = query.filter(BayesProfile.owner_id == owner_id).first()
            if user_profile:
                return user_profile
        return query.filter(BayesProfile.owner_id == None).first()

    def _serialize_bayes_samples(self, samples: List[BayesSample]) -> Dict[str, List[Dict[str, Any]]]:
        """将样本列表转换为兼容原 JSON 配置的 _samples 结构。"""
        buckets: Dict[str, List[Dict[str, Any]]] = {"可信": [], "不可信": []}
        for sample in samples:
            sample_id = str(sample.id) if sample.id else ""
            normalized_sample = {
                "id": sample_id,
                "name": sample.name or "样本",
                "vector": list(sample.vector or []),
                "label": int(sample.label or 0),
                "source": sample.source or "preset",
                "item_id": sample.item_id,
                "note": sample.note,
                "timestamp": sample.created_at.isoformat() if sample.created_at else "",
            }
            bucket = "可信" if int(sample.label or 0) == 1 else "不可信"
            buckets.setdefault(bucket, []).append(normalized_sample)
        return buckets

    def _extract_bayes_samples_from_payload(self, profile_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从配置 payload 中提取样本，便于落库。"""
        samples: List[Dict[str, Any]] = []
        raw_samples = profile_data.get("_samples")
        if not isinstance(raw_samples, dict):
            return samples

        for bucket, label in (("可信", 1), ("不可信", 0)):
            bucket_samples = raw_samples.get(bucket)
            if not isinstance(bucket_samples, list):
                continue
            for item in bucket_samples:
                if not isinstance(item, dict):
                    continue
                vector = item.get("vector")
                if not isinstance(vector, list):
                    continue
                try:
                    normalized_vector = [float(x) for x in vector]
                except (TypeError, ValueError):
                    continue
                samples.append(
                    {
                        "name": item.get("name") or "导入样本",
                        "vector": normalized_vector,
                        "label": label,
                        "source": str(item.get("source") or "preset"),
                        "item_id": item.get("item_id"),
                        "note": item.get("note"),
                    }
                )
        return samples

    def get_bayes_profile(self, version: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取贝叶斯配置（用户优先，系统回退，附带样本兼容字段）。"""
        normalized_version = str(version or "").replace(".json", "").strip()
        if not normalized_version:
            return None

        with self.get_session() as session:
            effective_profile = self._find_effective_bayes_profile(session, normalized_version, owner_id=owner_id)
            if not effective_profile:
                return None

            profile_dict = self._to_dict(effective_profile)
            sample_owner_conditions = []
            if owner_id:
                sample_owner_conditions.append(BayesSample.owner_id == owner_id)
            sample_owner_conditions.append(BayesSample.owner_id == None)
            samples = session.query(BayesSample).filter(
                BayesSample.profile_version == normalized_version,
                or_(*sample_owner_conditions)
            ).all()

            profile_dict["version"] = normalized_version
            profile_dict.setdefault("feature_names", list(self.DEFAULT_BAYES_FEATURE_NAMES))
            profile_dict["_samples"] = self._serialize_bayes_samples(samples)
            profile_dict.setdefault("_priors_mode", "auto_from_samples")
            profile_dict.setdefault("_stats_mode", "auto_from_samples")
            profile_dict.setdefault("_min_variance", 1e-4)
            return profile_dict
    
    def save_bayes_profile(self, profile_data: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存贝叶斯配置，并在提供 _samples 时同步样本。"""
        normalized_version = str(profile_data.get("version") or "bayes_v1").replace(".json", "").strip() or "bayes_v1"
        normalized_owner = str(owner_id).strip() if owner_id else None

        payload = {
            "owner_id": normalized_owner,
            "version": normalized_version,
            "display_name": profile_data.get("display_name") or normalized_version,
            "recommendation_fusion": profile_data.get("recommendation_fusion"),
            "bayes_feature_rules": profile_data.get("bayes_feature_rules"),
            "is_default": bool(profile_data.get("is_default", False)),
        }
        sample_payloads = self._extract_bayes_samples_from_payload(profile_data)

        with self.get_session() as session:
            existing = session.query(BayesProfile).filter(
                BayesProfile.version == normalized_version,
                BayesProfile.owner_id == normalized_owner
            ).first()

            if existing:
                existing.display_name = payload["display_name"]
                existing.recommendation_fusion = payload["recommendation_fusion"]
                existing.bayes_feature_rules = payload["bayes_feature_rules"]
                existing.is_default = payload["is_default"]
                profile_row = existing
            else:
                profile_row = BayesProfile(**payload)
                session.add(profile_row)
                session.flush()

            if "_samples" in profile_data:
                sample_query = session.query(BayesSample).filter(
                    BayesSample.profile_version == normalized_version
                )
                if normalized_owner:
                    sample_query = sample_query.filter(BayesSample.owner_id == normalized_owner)
                else:
                    sample_query = sample_query.filter(BayesSample.owner_id == None)
                sample_query.delete(synchronize_session=False)

                for sample_data in sample_payloads:
                    session.add(
                        BayesSample(
                            owner_id=normalized_owner,
                            profile_id=profile_row.id,
                            profile_version=normalized_version,
                            name=sample_data.get("name"),
                            vector=sample_data.get("vector") or [],
                            label=int(sample_data.get("label", 0)),
                            source=str(sample_data.get("source") or "preset"),
                            item_id=sample_data.get("item_id"),
                            note=sample_data.get("note"),
                        )
                    )

            session.flush()
            response_profile = self._to_dict(profile_row)
            sample_owner_conditions = []
            if normalized_owner:
                sample_owner_conditions.append(BayesSample.owner_id == normalized_owner)
            sample_owner_conditions.append(BayesSample.owner_id == None)
            current_samples = session.query(BayesSample).filter(
                BayesSample.profile_version == normalized_version,
                or_(*sample_owner_conditions)
            ).all()
            response_profile["version"] = normalized_version
            response_profile.setdefault("feature_names", list(self.DEFAULT_BAYES_FEATURE_NAMES))
            response_profile["_samples"] = self._serialize_bayes_samples(current_samples)
            response_profile.setdefault("_priors_mode", "auto_from_samples")
            response_profile.setdefault("_stats_mode", "auto_from_samples")
            response_profile.setdefault("_min_variance", 1e-4)
            return response_profile
    
    def list_bayes_profiles(self, owner_id: Optional[str] = None, include_system: bool = True) -> List[Dict[str, Any]]:
        """获取贝叶斯配置列表。"""
        with self.get_session() as session:
            query = session.query(BayesProfile)
            conditions = []
            if owner_id:
                conditions.append(BayesProfile.owner_id == owner_id)
            if include_system:
                conditions.append(BayesProfile.owner_id == None)

            if conditions:
                query = query.filter(or_(*conditions))
            elif owner_id is None:
                query = query.filter(BayesProfile.owner_id == None)

            profiles = query.all()
            return [self._to_dict(profile) for profile in profiles]

    def delete_bayes_profile(self, version: str, owner_id: Optional[str] = None) -> bool:
        """删除贝叶斯配置。"""
        normalized_version = str(version or "").replace(".json", "").strip()
        if not normalized_version:
            return False

        normalized_owner = str(owner_id).strip() if owner_id else None
        with self.get_session() as session:
            query = session.query(BayesProfile).filter(BayesProfile.version == normalized_version)
            if normalized_owner:
                query = query.filter(BayesProfile.owner_id == normalized_owner)
            else:
                query = query.filter(BayesProfile.owner_id == None)

            profile = query.first()
            if not profile:
                return False

            session.query(BayesSample).filter(
                BayesSample.profile_version == normalized_version,
                BayesSample.owner_id == (normalized_owner if normalized_owner else None)
            ).delete(synchronize_session=False)
            session.delete(profile)
            session.flush()
            return True

    # ============== Prompt 模板管理 ==============

    def list_prompt_templates(
        self,
        owner_id: Optional[str] = None,
        include_system: bool = True
    ) -> List[Dict[str, Any]]:
        """获取 Prompt 模板列表（用户模板优先，可包含系统模板）。"""
        with self.get_session() as session:
            records: List[PromptTemplate] = []
            if owner_id:
                records.extend(
                    session.query(PromptTemplate)
                    .filter(PromptTemplate.owner_id == owner_id)
                    .order_by(PromptTemplate.name.asc())
                    .all()
                )
            if include_system:
                records.extend(
                    session.query(PromptTemplate)
                    .filter(PromptTemplate.owner_id == None)
                    .order_by(PromptTemplate.name.asc())
                    .all()
                )

            dedup_by_name: Dict[str, Dict[str, Any]] = {}
            for record in records:
                normalized = self._to_dict(record)
                name = str(normalized.get("name") or "")
                if not name:
                    continue
                if name not in dedup_by_name:
                    dedup_by_name[name] = normalized
            return list(dedup_by_name.values())

    def get_prompt_template(self, name: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取 Prompt 模板（用户优先，系统回退）。"""
        normalized_name = self._normalize_prompt_template_name(name)
        with self.get_session() as session:
            if owner_id:
                user_template = session.query(PromptTemplate).filter(
                    PromptTemplate.owner_id == owner_id,
                    PromptTemplate.name == normalized_name
                ).first()
                if user_template:
                    return self._to_dict(user_template)

            system_template = session.query(PromptTemplate).filter(
                PromptTemplate.owner_id == None,
                PromptTemplate.name == normalized_name
            ).first()
            return self._to_dict(system_template)

    def save_prompt_template(self, template: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存 Prompt 模板。"""
        normalized_name = self._normalize_prompt_template_name(
            template.get("name") or template.get("filename") or template.get("id")
        )
        normalized_owner = str(owner_id).strip() if owner_id else None
        content = str(template.get("content") or "")
        is_default = bool(template.get("is_default", normalized_name == "base_prompt.txt"))

        with self.get_session() as session:
            existing = session.query(PromptTemplate).filter(
                PromptTemplate.owner_id == normalized_owner,
                PromptTemplate.name == normalized_name
            ).first()
            if existing:
                existing.content = content
                existing.is_default = is_default
                session.flush()
                return self._to_dict(existing)

            created = PromptTemplate(
                owner_id=normalized_owner,
                name=normalized_name,
                content=content,
                is_default=is_default,
            )
            session.add(created)
            session.flush()
            return self._to_dict(created)

    def delete_prompt_template(self, id_or_name: str, owner_id: Optional[str] = None) -> bool:
        """删除 Prompt 模板。"""
        identity = str(id_or_name or "").strip()
        if not identity:
            return False

        normalized_owner = str(owner_id).strip() if owner_id else None
        with self.get_session() as session:
            query = session.query(PromptTemplate)
            try:
                query = query.filter(PromptTemplate.id == UUID(identity))
            except (TypeError, ValueError):
                query = query.filter(PromptTemplate.name == self._normalize_prompt_template_name(identity))

            if normalized_owner:
                query = query.filter(PromptTemplate.owner_id == normalized_owner)
            else:
                query = query.filter(PromptTemplate.owner_id == None)

            count = query.delete(synchronize_session=False)
            return count > 0
    
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
