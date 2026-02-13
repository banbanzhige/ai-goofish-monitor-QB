"""
认证模块 v2.0 - 支持多用户 + RBAC

v1.0.0 升级：
- 支持 PostgreSQL 多用户认证
- 保持本地模式向下兼容（使用 .env 凭据）
- 基于角色的访问控制 (RBAC)
- 会话管理与审计日志
"""
import os
import time
import hashlib
import hmac
import json
import base64
import copy
from typing import Optional, List, Dict, Set
from functools import wraps
from fastapi import Request, Response, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.storage import get_storage
from src.storage.utils import verify_password, hash_token
from src.logging_config import get_logger
from src.config import STORAGE_BACKEND, WEB_USERNAME, WEB_PASSWORD


# 配置
SECRET_KEY = os.getenv("SECRET_KEY", "xianyu-monitor-default-secret-key-change-me")
SESSION_COOKIE_NAME = "session_token"
SESSION_EXPIRE_SECONDS = int(os.getenv("SESSION_EXPIRE_SECONDS", 7 * 24 * 60 * 60))  # 默认7天
RBAC_CONFIG_FILE = os.path.join("state", "rbac_config.json")

# logger
logger = get_logger(__name__, service="web")

# 角色权限定义（四级角色体系 v1.0.1，默认值）
DEFAULT_ROLES = {
    "super_admin": {"level": 4, "permissions": ["read", "write", "delete", "admin", "manage_users", "manage_system", "manage_admins"]},
    "admin": {"level": 3, "permissions": ["read", "write", "delete", "admin", "manage_users", "manage_system"]},
    "operator": {"level": 2, "permissions": ["read", "write", "delete"]},
    "viewer": {"level": 1, "permissions": ["read"]}
}

# 页面权限配置默认值
DEFAULT_PAGE_PERMISSIONS = {
    "tasks": ["viewer", "operator", "admin", "super_admin"],
    "accounts": ["operator", "admin", "super_admin"],
    "scheduled": ["operator", "admin", "super_admin"],
    "results": ["viewer", "operator", "admin", "super_admin"],
    "logs": ["viewer", "operator", "admin", "super_admin"],
    "notifications": ["operator", "admin", "super_admin"],
    "model-management": ["admin", "super_admin"],
    "settings": ["admin", "super_admin"],
    "user-data": ["viewer", "operator", "admin", "super_admin"]  # 我的资料Tab所有人可见
}

# 权限类别定义（V2 用户组权限）
PERMISSION_CATEGORIES = {
    "tasks": {"name": "任务", "desc": "任务创建、编辑、启停、调度管理"},
    "results": {"name": "结果", "desc": "结果查看、筛选、导出、删除"},
    "accounts": {"name": "账号", "desc": "平台账号与Cookie管理"},
    "notify": {"name": "通知", "desc": "通知渠道配置与测试"},
    "ai": {"name": "AI", "desc": "模型、Prompt、Bayes配置与反馈"},
    "admin": {"name": "管理", "desc": "用户管理、权限管理、系统设置"},
}

# 页面到类别映射（None=登录可访问，未映射=拒绝）
PAGE_CATEGORY_MAP = {
    "tasks": "tasks",
    "scheduled": "tasks",
    "results": "results",
    "logs": "results",
    "accounts": "accounts",
    "notifications": "notify",
    "model-management": "ai",
    "settings": "admin",
    "user-data": None,
}

# 角色回退类别（用于无用户组时向下兼容）
ROLE_CATEGORY_FALLBACK = {
    "super_admin": {"tasks", "results", "accounts", "notify", "ai", "admin"},
    "admin": {"tasks", "results", "accounts", "notify", "ai", "admin"},
    "operator": {"tasks", "results", "accounts", "notify"},
    "viewer": {"results"},
}

SYSTEM_GROUP_LEVEL = {
    "viewer_group": 1,
    "operator_group": 2,
    "admin_group": 3,
    "super_admin_group": 4,
}

# 运行时配置（支持热更新）
ROLES = copy.deepcopy(DEFAULT_ROLES)
PAGE_PERMISSIONS = copy.deepcopy(DEFAULT_PAGE_PERMISSIONS)
ALLOWED_PERMISSION_SET = set(
    permission
    for role_info in DEFAULT_ROLES.values()
    for permission in role_info.get("permissions", [])
)
DEFAULT_ROLE_ORDER = ["super_admin", "admin", "operator", "viewer"]


def _apply_runtime_rbac_config(rbac_config: dict):
    """将 RBAC 配置应用到运行时对象，保持引用不变以兼容其他模块导入。"""
    roles = rbac_config.get("roles", {})
    page_permissions = rbac_config.get("page_permissions", {})
    ROLES.clear()
    ROLES.update(copy.deepcopy(roles))
    PAGE_PERMISSIONS.clear()
    PAGE_PERMISSIONS.update(copy.deepcopy(page_permissions))


def _build_default_rbac_config() -> dict:
    """构建默认 RBAC 配置。"""
    return {
        "roles": copy.deepcopy(DEFAULT_ROLES),
        "page_permissions": copy.deepcopy(DEFAULT_PAGE_PERMISSIONS)
    }


def _validate_rbac_config(rbac_config: dict) -> dict:
    """校验并标准化 RBAC 配置，避免非法配置导致系统不可用。"""
    if not isinstance(rbac_config, dict):
        raise ValueError("RBAC 配置格式错误：必须是对象")

    roles = rbac_config.get("roles")
    page_permissions = rbac_config.get("page_permissions")
    if not isinstance(roles, dict) or not isinstance(page_permissions, dict):
        raise ValueError("RBAC 配置缺少 roles 或 page_permissions")

    role_keys = set(DEFAULT_ROLES.keys())
    if set(roles.keys()) != role_keys:
        raise ValueError(f"角色集合必须固定为: {sorted(role_keys)}")

    normalized_roles = {}
    for role_name in DEFAULT_ROLE_ORDER:
        role_info = roles.get(role_name, {})
        if not isinstance(role_info, dict):
            raise ValueError(f"角色 {role_name} 配置格式错误")

        level = role_info.get("level")
        if not isinstance(level, int):
            raise ValueError(f"角色 {role_name} 的 level 必须是整数")

        raw_permissions = role_info.get("permissions", [])
        if not isinstance(raw_permissions, list):
            raise ValueError(f"角色 {role_name} 的 permissions 必须是数组")

        unknown_permissions = [p for p in raw_permissions if p not in ALLOWED_PERMISSION_SET]
        if unknown_permissions:
            raise ValueError(f"角色 {role_name} 含有未知权限: {unknown_permissions}")

        dedup_permissions = sorted(set(raw_permissions))
        normalized_roles[role_name] = {
            "level": level,
            "permissions": dedup_permissions
        }

    # 关键等级关系约束，防止等级错配造成权限失效
    if not (
        normalized_roles["super_admin"]["level"] > normalized_roles["admin"]["level"] >
        normalized_roles["operator"]["level"] > normalized_roles["viewer"]["level"]
    ):
        raise ValueError("角色等级必须满足 super_admin > admin > operator > viewer")

    # 关键权限兜底，防止管理能力被误删
    required_super_admin_permissions = {"manage_admins", "manage_users", "manage_system"}
    super_admin_permissions = set(normalized_roles["super_admin"]["permissions"])
    if not required_super_admin_permissions.issubset(super_admin_permissions):
        raise ValueError("super_admin 必须包含 manage_admins/manage_users/manage_system 权限")

    role_names = set(normalized_roles.keys())
    page_keys = set(DEFAULT_PAGE_PERMISSIONS.keys())
    if set(page_permissions.keys()) != page_keys:
        raise ValueError(f"页面集合必须固定为: {sorted(page_keys)}")

    normalized_pages = {}
    for page_name in sorted(page_permissions.keys()):
        allowed_roles = page_permissions.get(page_name, [])
        if not isinstance(allowed_roles, list):
            raise ValueError(f"页面 {page_name} 的角色配置必须是数组")

        unknown_roles = [r for r in allowed_roles if r not in role_names]
        if unknown_roles:
            raise ValueError(f"页面 {page_name} 含有未知角色: {unknown_roles}")

        dedup_roles = sorted(set(allowed_roles), key=lambda x: DEFAULT_ROLE_ORDER.index(x))
        if not dedup_roles:
            raise ValueError(f"页面 {page_name} 至少要允许一个角色访问")
        normalized_pages[page_name] = dedup_roles

    return {
        "roles": normalized_roles,
        "page_permissions": normalized_pages
    }


def _load_rbac_config_from_file() -> dict:
    """从磁盘加载 RBAC 配置；失败时自动回退默认配置。"""
    default_config = _build_default_rbac_config()
    if not os.path.exists(RBAC_CONFIG_FILE):
        return default_config

    try:
        with open(RBAC_CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        return _validate_rbac_config(loaded)
    except Exception as e:
        logger.warning(
            "加载 RBAC 配置失败，已回退到默认配置",
            extra={"event": "rbac_config_load_failed", "path": RBAC_CONFIG_FILE},
            exc_info=e
        )
        return default_config


def _save_rbac_config_to_file(rbac_config: dict):
    """将 RBAC 配置写入磁盘。"""
    os.makedirs(os.path.dirname(RBAC_CONFIG_FILE), exist_ok=True)
    with open(RBAC_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(rbac_config, f, ensure_ascii=False, indent=2)


def reload_rbac_config() -> dict:
    """重载 RBAC 配置。"""
    normalized = _load_rbac_config_from_file()
    _apply_runtime_rbac_config(normalized)
    return get_rbac_config()


def get_rbac_config() -> dict:
    """获取当前生效的 RBAC 配置快照。"""
    return {
        "roles": copy.deepcopy(ROLES),
        "page_permissions": copy.deepcopy(PAGE_PERMISSIONS)
    }


def update_rbac_config(roles: dict, page_permissions: dict) -> dict:
    """更新并持久化 RBAC 配置。"""
    normalized = _validate_rbac_config({
        "roles": roles,
        "page_permissions": page_permissions
    })
    _save_rbac_config_to_file(normalized)
    _apply_runtime_rbac_config(normalized)
    return get_rbac_config()

# 启动时加载一次 RBAC 配置
reload_rbac_config()


def get_page_permissions() -> dict:
    """获取页面权限配置"""
    return copy.deepcopy(PAGE_PERMISSIONS)


def get_role_fallback_categories(role: str) -> Set[str]:
    """基于旧角色体系返回回退类别集合。"""
    return set(ROLE_CATEGORY_FALLBACK.get((role or "viewer"), ROLE_CATEGORY_FALLBACK["viewer"]))


def get_user_groups(user: Optional[dict]) -> List[Dict]:
    """获取用户所属用户组，单体系模式下作为权限唯一来源。"""
    if not user:
        return []

    if not is_multi_user_mode():
        return [{
            "id": "local-super-admin-group",
            "code": "super_admin_group",
            "name": "本地超级管理员组",
            "permissions": [
                {"category": "tasks", "enabled": True},
                {"category": "results", "enabled": True},
                {"category": "accounts", "enabled": True},
                {"category": "notify", "enabled": True},
                {"category": "ai", "enabled": True},
                {"category": "admin", "enabled": True},
            ]
        }]

    user_id = user.get("user_id") or user.get("id")
    if not user_id:
        return []

    storage = get_storage()
    return storage.get_user_groups(str(user_id))


def get_user_categories(user: Optional[dict]) -> Set[str]:
    """
    获取用户权限类别集合。
    单体系模式下仅从用户组聚合权限类别。
    """
    if not user:
        return set()

    try:
        groups = get_user_groups(user)
        if not groups:
            return set()
        categories: Set[str] = set()
        for group in groups:
            for permission in group.get("permissions", []):
                category = permission.get("category")
                if permission.get("enabled") and category in PERMISSION_CATEGORIES:
                    categories.add(category)
        return categories
    except Exception as e:
        logger.warning(
            "获取用户组权限失败",
            extra={"event": "group_permission_load_failed", "user_id": user.get("user_id") or user.get("id")},
            exc_info=e
        )
        return set()


def has_category(user: Optional[dict], category: str) -> bool:
    """检查用户是否具备指定类别权限。"""
    if category not in PERMISSION_CATEGORIES:
        return False
    return category in get_user_categories(user)


def can_access_page(user: dict, page: str) -> bool:
    """检查用户是否有权限访问指定页面。"""
    if not user:
        return False

    required_category = PAGE_CATEGORY_MAP.get(page, "__UNMAPPED__")
    if required_category == "__UNMAPPED__":
        return False
    if required_category is None:
        return True
    return has_category(user, required_category)


def get_storage_backend() -> str:
    """获取当前存储后端类型"""
    return STORAGE_BACKEND()


def is_multi_user_mode() -> bool:
    """检查是否为多用户模式（PostgreSQL）"""
    return get_storage_backend() == 'postgres'


def get_auth_credentials():
    """从环境变量获取认证凭据（本地模式）"""
    username = WEB_USERNAME()
    password = WEB_PASSWORD()
    username = username or "admin"
    password = password or "admin123"
    return username, password


def is_auth_required() -> bool:
    """检查是否需要认证"""
    if is_multi_user_mode():
        return True  # 多用户模式始终需要认证
    username, password = get_auth_credentials()
    return bool(username and password)


def verify_user(username: str, password: str) -> Optional[dict]:
    """
    验证用户凭据
    
    多用户模式：从数据库查询
    本地模式：从 .env 读取
    
    返回用户信息字典或 None
    """
    if is_multi_user_mode():
        # 多用户模式：从数据库验证
        storage = get_storage()
        user = storage.get_user_by_username(username)
        
        if user and user.get('password_hash'):
            if verify_password(password, user['password_hash']):
                # 更新最后登录时间
                storage.update_user(user['id'], {'last_login_at': time.strftime('%Y-%m-%dT%H:%M:%SZ')})
                
                return {
                    "user_id": str(user['id']),
                    "username": user['username'],
                    "role": user.get('role', 'viewer'),
                    "email": user.get('email'),
                    "is_active": user.get('is_active', True)
                }
        return None
    else:
        # 本地模式：从 .env 验证
        expected_username, expected_password = get_auth_credentials()
        
        if username == expected_username and password == expected_password:
            return {
                "user_id": "local_admin",
                "username": username,
                "role": "super_admin",  # 本地模式始终为超级管理员
                "is_active": True
            }
        return None


def _sign_data(data: str) -> str:
    """对数据进行HMAC签名"""
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


def create_session_token(user_data: dict) -> str:
    """
    创建签名的session token
    格式: base64(json_data).signature
    """
    session_data = {
        **user_data,
        "login_time": int(time.time()),
        "expires": int(time.time()) + SESSION_EXPIRE_SECONDS
    }
    json_data = json.dumps(session_data, ensure_ascii=False)
    encoded_data = base64.urlsafe_b64encode(json_data.encode('utf-8')).decode('utf-8')
    signature = _sign_data(encoded_data)
    return f"{encoded_data}.{signature}"


def verify_session_token(token: str) -> Optional[dict]:
    """
    验证并解析session token
    返回用户数据或None
    """
    if not token or '.' not in token:
        return None
    
    try:
        encoded_data, signature = token.rsplit('.', 1)
        
        # 验证签名
        expected_signature = _sign_data(encoded_data)
        if not hmac.compare_digest(signature, expected_signature):
            return None
        
        # 解析数据
        json_data = base64.urlsafe_b64decode(encoded_data.encode('utf-8')).decode('utf-8')
        session_data = json.loads(json_data)
        
        # 检查过期
        if session_data.get('expires', 0) < int(time.time()):
            return None
        
        # 多用户模式：验证用户是否仍然有效
        if is_multi_user_mode():
            storage = get_storage()
            user = storage.get_user_by_id(session_data.get('user_id'))
            if not user or not user.get('is_active', True):
                return None
        
        return session_data
    except Exception:
        return None


def get_current_user(request: Request) -> Optional[dict]:
    """
    从Cookie获取当前登录用户
    返回用户数据或None
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return verify_session_token(token)


def require_auth(request: Request) -> Optional[dict]:
    """
    检查认证状态，未登录则返回None
    用于路由依赖
    """
    if not is_auth_required():
        return {"user_id": "anonymous", "username": "anonymous", "role": "super_admin"}
    return get_current_user(request)


def require_role(required_roles: List[str]):
    """
    角色验证装饰器
    
    用法:
        @app.get("/admin")
        @require_role(["admin"])
        async def admin_only(request: Request):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = get_current_user(request)
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未登录，请先登录"
                )
            
            user_role = user.get('role', 'viewer')
            user_level = ROLES.get(user_role, ROLES['viewer']).get('level', 1)
            required_levels = [
                ROLES.get(role, ROLES['viewer']).get('level', 1)
                for role in required_roles
            ]
            required_min_level = min(required_levels) if required_levels else 999

            # 角色按等级向下兼容：高等级角色可访问低等级资源
            if user_level < required_min_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"权限不足，需要 {required_roles} 角色"
                )
            
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_category(category: str):
    """类别权限装饰器（V2 用户组权限）。"""
    if category not in PERMISSION_CATEGORIES:
        raise ValueError(f"未知权限类别: {category}")

    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = get_current_user(request)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未登录，请先登录"
                )

            if not has_category(user, category):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"权限不足，需要 {PERMISSION_CATEGORIES[category]['name']} 权限"
                )

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def check_permission(user: dict, permission: str) -> bool:
    """
    检查用户是否有指定权限
    
    Args:
        user: 用户数据字典
        permission: 权限名称 (read, write, delete, admin, manage_users, manage_system)
    
    Returns:
        bool: 是否有权限
    """
    if not user:
        return False

    permission_category_map = {
        "admin": "admin",
        "manage_users": "admin",
        "manage_system": "admin",
        "manage_admins": "admin",
    }
    mapped_category = permission_category_map.get(permission)
    if mapped_category:
        return has_category(user, mapped_category)

    user_categories = get_user_categories(user)
    if permission == "read":
        return bool(user_categories)
    if permission in {"write", "delete"}:
        return bool(user_categories - {"results"})
    return False


def get_user_management_level(user: Optional[dict]) -> int:
    """获取用户管理等级（基于系统组，不再依赖 role 判权）。"""
    if not user:
        return 0
    if not is_multi_user_mode():
        return 4

    try:
        groups = get_user_groups(user)
        levels = [
            SYSTEM_GROUP_LEVEL.get((group.get("code") or "").lower(), 0)
            for group in groups
        ]
        return max(levels) if levels else 0
    except Exception:
        return 0


def get_user_role_level(user: dict) -> int:
    """兼容函数：返回用户管理等级。"""
    return get_user_management_level(user)


def set_session_cookie(response: Response, user_data: dict):
    """设置session cookie"""
    token = create_session_token(user_data)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_EXPIRE_SECONDS,
        httponly=True,
        samesite="lax"
    )


def clear_session_cookie(response: Response):
    """清除session cookie"""
    response.delete_cookie(key=SESSION_COOKIE_NAME)


def log_audit_action(user: dict, action: str, resource_type: str, 
                     resource_id: str = None, details: dict = None,
                     ip_address: str = None):
    """
    记录审计日志
    
    仅在多用户模式下记录
    """
    if not is_multi_user_mode():
        return
    
    try:
        storage = get_storage()
        storage.log_audit(
            user_id=user.get('user_id'),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
    except Exception:
        pass  # 审计日志失败不应影响主流程


# ============== 兼容旧的Basic Auth（静态文件用）==============

class AuthenticatedStaticFiles(StaticFiles):
    """自定义静态文件处理器，支持Cookie认证"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def __call__(self, scope, receive, send):
        # 如果不需要认证，直接放行
        if not is_auth_required():
            await super().__call__(scope, receive, send)
            return

        # 从Cookie检查认证
        headers = dict(scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode()
        
        # 解析Cookie
        session_token = None
        for cookie in cookie_header.split(";"):
            cookie = cookie.strip()
            if cookie.startswith(f"{SESSION_COOKIE_NAME}="):
                session_token = cookie[len(SESSION_COOKIE_NAME) + 1:]
                break
        
        if session_token and verify_session_token(session_token):
            await super().__call__(scope, receive, send)
            return
        
        # 未认证，重定向到登录页
        await send({
            "type": "http.response.start",
            "status": 302,
            "headers": [
                (b"location", b"/login"),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": b"",
        })


# ============== 用户注册相关 ==============

def create_user(username: str, password: str, email: str = None, role: str = "operator") -> Optional[dict]:
    """
    创建新用户（仅多用户模式）
    
    Args:
        username: 用户名
        password: 密码（明文，会自动哈希）
        email: 邮箱
        role: 角色 (admin/operator/viewer)
    
    Returns:
        创建的用户信息或 None
    """
    if not is_multi_user_mode():
        raise ValueError("本地模式不支持创建用户")
    
    storage = get_storage()
    
    # 检查用户名是否已存在
    existing = storage.get_user_by_username(username)
    if existing:
        raise ValueError(f"用户名 {username} 已存在")
    
    # 验证角色
    if role not in ROLES:
        raise ValueError(f"无效的角色: {role}")
    
    return storage.create_user({
        "username": username,
        "password": password,
        "email": email,
        "role": role,
        "is_active": True
    })
