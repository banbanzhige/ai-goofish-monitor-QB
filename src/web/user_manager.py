"""
用户管理 API - v1.0.0

提供用户 CRUD、会话管理、API 配置、通知配置、平台账号管理等接口。
支持多用户数据隔离。
"""
import os
import io
import base64
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, status, Depends, Query, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr
from PIL import Image

from .auth import (
    get_current_user, require_auth, check_permission, 
    is_multi_user_mode, log_audit_action, ROLES, PAGE_PERMISSIONS,
    get_rbac_config, can_access_page, get_user_categories, has_category,
    get_user_management_level
)
from src.storage import get_storage
from src.config import WEB_USERNAME, WEB_PASSWORD, STORAGE_BACKEND
from src.logging_config import get_logger
from src.storage.utils import verify_password


router = APIRouter(prefix="/api/users", tags=["users"])
groups_router = APIRouter(prefix="/api/groups", tags=["groups"])
logger = get_logger(__name__, service="web")
SYSTEM_GROUP_ROLE_MAP = {
    "super_admin_group": "super_admin",
    "admin_group": "admin",
    "operator_group": "operator",
    "viewer_group": "viewer",
}
SYSTEM_GROUP_LEVEL_MAP = {
    "viewer_group": 1,
    "operator_group": 2,
    "admin_group": 3,
    "super_admin_group": 4,
}
SYSTEM_GROUP_CODES = set(SYSTEM_GROUP_LEVEL_MAP.keys())


# ============== Pydantic 模型 ==============

class UserCreate(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None
    group_ids: List[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    """更新用户请求"""
    email: Optional[str] = None
    is_active: Optional[bool] = None
    group_ids: Optional[List[str]] = None


class PasswordChange(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str = Field(..., min_length=6)


class UserPasswordReset(BaseModel):
    """管理员重置用户密码请求"""
    new_password: str = Field(..., min_length=6)
    revoke_sessions: bool = True


class ProfileUpdate(BaseModel):
    """更新个人资料请求"""
    email: Optional[str] = None


class RbacConfigUpdate(BaseModel):
    """RBAC 配置更新请求"""
    roles: Dict[str, Any]
    page_permissions: Dict[str, List[str]]


class UserGroupCreate(BaseModel):
    """创建用户组请求"""
    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    permissions: Dict[str, bool] = Field(default_factory=dict)


class UserGroupUpdate(BaseModel):
    """更新用户组请求"""
    code: Optional[str] = Field(default=None, min_length=2, max_length=64)
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = None
    permissions: Optional[Dict[str, bool]] = None


class GroupPermissionUpdate(BaseModel):
    """用户组权限更新请求"""
    categories: Dict[str, bool] = Field(default_factory=dict)


class UserGroupAssignment(BaseModel):
    """用户组分配请求"""
    group_ids: List[str] = Field(default_factory=list)


class ApiConfigCreate(BaseModel):
    """API 配置创建"""
    provider: str = Field(..., description="提供商: openai, azure, ollama, custom")
    name: str = Field(..., description="配置名称")
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    model: Optional[str] = None
    is_default: bool = False


class NotificationConfigCreate(BaseModel):
    """通知配置创建"""
    channel_type: str = Field(..., description="渠道类型: ntfy, bark, telegram, etc.")
    name: str = Field(..., description="配置名称")
    config: dict = Field(default_factory=dict, description="渠道配置")
    is_enabled: bool = True
    notify_on_complete: bool = True
    notify_on_recommend: bool = True


class NotificationConfigUpdate(BaseModel):
    """通知配置更新"""
    name: Optional[str] = None
    config: Optional[dict] = None
    is_enabled: Optional[bool] = None
    notify_on_complete: Optional[bool] = None
    notify_on_recommend: Optional[bool] = None


class PlatformAccountCreate(BaseModel):
    """平台账号创建"""
    platform: str = Field(default="goofish")
    display_name: str
    cookies: Optional[str] = None


# ============== 依赖项 ==============

async def get_current_user_required(request: Request) -> dict:
    """获取当前用户（必须登录）"""
    user = require_auth(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录，请先登录"
        )
    return user


async def require_admin(request: Request) -> dict:
    """要求管理员权限"""
    user = await get_current_user_required(request)
    if not check_permission(user, "manage_users"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return user


def ensure_admin_scope(
    operator_user: dict,
    storage,
    target_user: Optional[dict] = None,
    target_group_ids: Optional[List[str]] = None
):
    """
    校验管理员可操作范围（用户组单体系）。
    规则：
    - 管理等级 4（super_admin_group）可管理所有用户与用户组。
    - 管理等级 3（admin_group）仅可管理等级 < 4 的用户，且不可分配 admin/super_admin 系统组。
    """
    operator_level = get_user_management_level(operator_user)
    if operator_level >= 4:
        return

    if operator_level < 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )

    if target_user:
        target_user_id = target_user.get("id") or target_user.get("user_id")
        if target_user_id:
            target_groups = storage.get_user_groups(str(target_user_id))
            target_level = max([
                SYSTEM_GROUP_LEVEL_MAP.get((group.get("code") or "").lower(), 0)
                for group in target_groups
            ] or [0])
            if target_level >= 4:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="仅超级管理员可管理超级管理员用户"
                )

    if target_group_ids:
        for group_id in target_group_ids:
            group = storage.get_user_group(group_id)
            if not group:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"用户组不存在: {group_id}")
            group_code = (group.get("code") or "").lower()
            if group_code in {"admin_group", "super_admin_group"}:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="仅超级管理员可分配管理员系统组"
                )


def ensure_group_permission_edit_scope(operator_user: dict, target_group: Dict[str, Any]):
    """
    校验组权限矩阵写入边界。
    规则：
    - 系统预置4组（super/admin/operator/viewer）仅超级管理员可修改权限。
    - 自定义用户组允许管理员修改权限。
    """
    if not target_group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户组不存在"
        )

    group_code = str(target_group.get("code") or "").lower()
    is_system_group = bool(target_group.get("is_system")) or group_code in SYSTEM_GROUP_CODES
    if not is_system_group:
        return

    if get_user_management_level(operator_user) < 4:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅超级管理员可修改系统预置组权限"
        )


def build_super_admin_password_notice(user: dict, storage=None) -> Optional[str]:
    """构建超级管理员默认密码提醒。"""
    if not user:
        return None

    if get_user_management_level(user) < 4:
        return None

    username = str(user.get("username") or "").strip()
    if not username:
        return None

    if not is_multi_user_mode():
        if (WEB_PASSWORD() or "") == "admin123":
            return "安全提醒：当前超级管理员仍在使用默认密码，请尽快在“用户数据 > 修改密码”中更新密码。"
        return None

    current_storage = storage or get_storage()
    db_user = current_storage.get_user_by_username(username)
    if not db_user:
        return None

    password_hash = str(db_user.get("password_hash") or "")
    if password_hash and verify_password("admin123", password_hash):
        return "安全提醒：当前超级管理员仍在使用默认密码，请尽快在“用户数据 > 修改密码”中更新密码。"
    return None


def _infer_legacy_role_from_groups(groups: List[Dict[str, Any]]) -> str:
    """根据系统组推断兼容 role 字段，避免影响历史展示。"""
    highest_level = 0
    inferred_role = "viewer"
    for group in groups or []:
        group_code = (group.get("code") or "").lower()
        level = SYSTEM_GROUP_LEVEL_MAP.get(group_code, 0)
        if level > highest_level:
            highest_level = level
            inferred_role = SYSTEM_GROUP_ROLE_MAP.get(group_code, "viewer")
    return inferred_role


def get_available_permissions(roles_config: dict) -> List[str]:
    """从角色配置中提取权限全集，用于前端角色管理展示。"""
    permission_set = set()
    for role_info in roles_config.values():
        if isinstance(role_info, dict):
            permissions = role_info.get("permissions", [])
            if isinstance(permissions, list):
                permission_set.update(str(p) for p in permissions)
    return sorted(permission_set)


# ============== 用户管理接口 ==============

@router.get("/me")
async def get_my_profile(user: dict = Depends(get_current_user_required)):
    """获取当前用户信息"""
    if not is_multi_user_mode():
        categories = sorted(list(get_user_categories(user)))
        security_notice = build_super_admin_password_notice(user)
        return {
            "user_id": user.get("user_id"),
            "username": user.get("username"),
            "role": user.get("role"),
            "is_multi_user_mode": False,
            "categories": categories,
            "management_level": 4,
            "groups": [{"id": "local-super-admin-group", "code": "super_admin_group", "name": "本地超级管理员组"}],
            "security_notice": security_notice
        }
    
    storage = get_storage()
    full_user = storage.get_user_by_id(user.get("user_id"))
    
    if not full_user:
        return user

    try:
        user_groups = storage.get_user_groups(user.get("user_id"))
    except Exception as e:
        logger.warning(
            "获取用户组失败，已降级为空列表",
            extra={"event": "user_groups_load_failed", "user_id": user.get("user_id")},
            exc_info=e
        )
        user_groups = []
    categories = sorted(list(get_user_categories(user)))
    management_level = get_user_management_level(user)
    security_notice = build_super_admin_password_notice(user, storage=storage)
    
    return {
        **full_user,
        "role": _infer_legacy_role_from_groups(user_groups),
        "is_multi_user_mode": True,
        "permissions": [],
        "management_level": management_level,
        "categories": categories,
        "security_notice": security_notice,
        "groups": [
            {"id": group.get("id"), "code": group.get("code"), "name": group.get("name")}
            for group in user_groups
        ]
    }


@router.put("/me/password")
async def change_my_password(
    data: PasswordChange,
    request: Request,
    user: dict = Depends(get_current_user_required)
):
    """修改当前用户密码"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式请直接修改 .env 文件中的 WEB_PASSWORD"
        )
    
    storage = get_storage()
    
    # 验证旧密码
    db_user = storage.get_user_by_username(user.get("username"))
    if not db_user or not verify_password(data.old_password, db_user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )
    
    # 更新密码
    storage.update_user(user.get("user_id"), {"password": data.new_password})
    
    log_audit_action(user, "change_password", "user", user.get("user_id"), 
                     ip_address=request.client.host if request.client else None)
    
    return {"message": "密码修改成功"}


@router.put("/{user_id}/password")
async def reset_user_password(
    user_id: str,
    data: UserPasswordReset,
    request: Request,
    user: dict = Depends(require_admin)
):
    """重置指定用户密码（仅超级管理员，且仅限其他账号）"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式不支持多用户密码重置"
        )

    if get_user_management_level(user) < 4:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅超级管理员可重置其他用户密码"
        )

    current_user_id = str(user.get("user_id") or "")
    if current_user_id and str(user_id) == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请使用“修改我的密码”接口更新当前登录账号密码"
        )

    storage = get_storage()
    target_user = storage.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    ensure_admin_scope(user, storage=storage, target_user=target_user)
    storage.update_user(user_id, {"password": data.new_password})

    revoked_count = 0
    if data.revoke_sessions:
        try:
            revoked_count = int(storage.delete_user_sessions(user_id) or 0)
        except Exception as exc:
            logger.warning(
                "重置密码后清理会话失败",
                extra={"event": "admin_reset_password_revoke_sessions_failed", "target_user_id": user_id},
                exc_info=exc
            )

    log_audit_action(
        user,
        "reset_user_password",
        "user",
        user_id,
        details={
            "target_username": target_user.get("username"),
            "revoke_sessions": bool(data.revoke_sessions),
            "revoked_sessions": revoked_count,
        },
        ip_address=request.client.host if request.client else None
    )

    return {
        "message": "用户密码已重置",
        "revoked_sessions": revoked_count if data.revoke_sessions else 0
    }


@router.get("")
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: dict = Depends(require_admin)
):
    """获取用户列表（管理员）"""
    if not is_multi_user_mode():
        # 本地模式返回单用户
        return {
            "users": [{
                "user_id": "local_admin",
                "username": WEB_USERNAME(),
                "role": "super_admin",
                "is_active": True
            }],
            "total": 1
        }
    
    storage = get_storage()
    users = storage.list_users(skip=skip, limit=limit)

    for item in users:
        user_id = item.get("id") or item.get("user_id")
        groups = storage.get_user_groups(str(user_id))
        item["groups"] = [
            {"id": group.get("id"), "code": group.get("code"), "name": group.get("name")}
            for group in groups
        ]
        item["group_ids"] = [group.get("id") for group in groups if group.get("id")]
        item["role"] = _infer_legacy_role_from_groups(groups)
    
    return {
        "users": users,
        "total": len(users)  # TODO: 添加 count 方法
    }


@router.post("")
async def create_user(
    data: UserCreate,
    request: Request,
    user: dict = Depends(require_admin)
):
    """创建新用户（管理员）"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式不支持多用户"
        )
    
    storage = get_storage()
    if not data.group_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少选择一个用户组")
    ensure_admin_scope(user, storage=storage, target_group_ids=data.group_ids)
    
    # 检查用户名是否已存在
    existing = storage.get_user_by_username(data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"用户名 {data.username} 已存在"
        )
    
    new_user = storage.create_user({
        "username": data.username,
        "password": data.password,
        "email": data.email,
        "role": "viewer",
        "is_active": True
    })

    try:
        storage.set_user_groups(new_user.get("id"), data.group_ids)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    groups = storage.get_user_groups(new_user.get("id"))
    new_user["role"] = _infer_legacy_role_from_groups(groups)
    
    log_audit_action(user, "create_user", "user", new_user.get("id"),
                     details={"username": data.username, "group_ids": data.group_ids},
                     ip_address=request.client.host if request.client else None)

    new_user["groups"] = [{"id": group.get("id"), "code": group.get("code"), "name": group.get("name")} for group in groups]
    new_user["group_ids"] = [group.get("id") for group in groups if group.get("id")]
    return {"message": "用户创建成功", "user": new_user}


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    data: UserUpdate,
    request: Request,
    user: dict = Depends(require_admin)
):
    """更新用户信息（管理员）"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式不支持多用户"
        )
    
    storage = get_storage()
    
    target_user = storage.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 管理边界：用户组单一体系
    ensure_admin_scope(user, storage=storage, target_user=target_user)

    updates = {k: v for k, v in data.dict().items() if v is not None}
    group_ids = updates.pop("group_ids", None)
    updates.pop("role", None)
    if group_ids is not None:
        if len(group_ids) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少保留一个用户组")
        ensure_admin_scope(user, storage=storage, target_group_ids=group_ids)
    if not updates:
        if group_ids is None:
            return {"message": "无更新内容", "user": target_user}

    updated = storage.update_user(user_id, updates)
    if group_ids is not None:
        try:
            storage.set_user_groups(user_id, group_ids)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    details = {**updates}
    if group_ids is not None:
        details["group_ids"] = group_ids
    log_audit_action(user, "update_user", "user", user_id, details=details,
                     ip_address=request.client.host if request.client else None)
    groups = storage.get_user_groups(user_id)
    updated["groups"] = [{"id": group.get("id"), "code": group.get("code"), "name": group.get("name")} for group in groups]
    updated["group_ids"] = [group.get("id") for group in groups if group.get("id")]
    updated["role"] = _infer_legacy_role_from_groups(groups)
    return {"message": "用户更新成功", "user": updated}


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    request: Request,
    user: dict = Depends(require_admin)
):
    """删除用户（管理员）"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式不支持多用户"
        )
    
    # 不能删除自己
    if user_id == user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账号"
        )
    
    storage = get_storage()
    
    target_user = storage.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 管理边界：用户组单一体系
    ensure_admin_scope(user, storage=storage, target_user=target_user)
    
    # 删除用户的所有会话
    storage.delete_user_sessions(user_id)
    
    # 删除用户
    storage.delete_user(user_id)
    
    log_audit_action(user, "delete_user", "user", user_id,
                     details={"username": target_user.get("username")},
                     ip_address=request.client.host if request.client else None)
    
    return {"message": "用户删除成功"}


class SwitchAccountRequest(BaseModel):
    """切换账号请求"""
    user_id: str


@router.post("/switch")
async def switch_account(
    data: SwitchAccountRequest,
    request: Request,
    user: dict = Depends(require_admin)
):
    """切换到其他账号（仅管理员）"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式不支持切换账号"
        )
    
    # 不能切换到自己
    if data.user_id == user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已经是当前账号"
        )
    
    storage = get_storage()
    
    # 获取目标用户
    target_user = storage.get_user_by_id(data.user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="目标用户不存在"
        )
    
    # 检查目标用户是否已启用
    if not target_user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目标账号已被禁用"
        )
    
    # 管理边界：用户组单一体系
    ensure_admin_scope(user, storage=storage, target_user=target_user)
    
    # 创建新会话
    import secrets
    session_token = secrets.token_urlsafe(32)
    session = storage.create_session(
        user_id=data.user_id,
        token=session_token,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建会话失败"
        )
    
    log_audit_action(user, "switch_account", "user", data.user_id,
                     details={"target_username": target_user.get("username")},
                     ip_address=request.client.host if request.client else None)
    
    # 返回新的 session token，前端会设置 cookie 并刷新页面
    response = JSONResponse({
        "message": "切换成功",
        "username": target_user.get("username")
    })
    
    # 设置新的 session cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        max_age=86400 * 7,  # 7 天
        samesite="lax"
    )
    
    return response


# ============== API 配置管理 ==============

@router.get("/me/api-configs")
async def get_my_api_configs(user: dict = Depends(get_current_user_required)):
    """获取我的 API 配置列表"""
    storage = get_storage()

    if not is_multi_user_mode():
        # 本地模式从统一存储层读取，确保与资产统计口径一致
        user_id = str(user.get("user_id") or user.get("id") or "local_admin")
        configs = storage.get_user_api_configs(user_id)
        return {
            "configs": configs,
            "message": "本地模式API配置在系统设置中管理"
        }
    
    configs = storage.get_user_api_configs(user.get("user_id"))
    
    return {"configs": configs}


@router.post("/me/api-configs")
async def create_my_api_config(
    data: ApiConfigCreate,
    request: Request,
    user: dict = Depends(get_current_user_required)
):
    """创建新的 API 配置"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式请直接修改 .env 文件"
        )
    
    storage = get_storage()
    config = storage.save_user_api_config(user.get("user_id"), data.dict())
    
    log_audit_action(user, "create_api_config", "api_config", config.get("id"),
                     ip_address=request.client.host if request.client else None)
    
    return {"message": "API 配置创建成功", "config": config}


@router.delete("/me/api-configs/{config_id}")
async def delete_my_api_config(
    config_id: str,
    request: Request,
    user: dict = Depends(get_current_user_required)
):
    """删除 API 配置"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式无法删除配置"
        )
    
    storage = get_storage()
    deleted = storage.delete_user_api_config(config_id, user.get("user_id"))
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    log_audit_action(user, "delete_api_config", "api_config", config_id,
                     ip_address=request.client.host if request.client else None)
    
    return {"message": "配置删除成功"}


# ============== 通知配置管理 ==============

@router.get("/me/notification-configs")
async def get_my_notification_configs(user: dict = Depends(get_current_user_required)):
    """获取我的通知配置列表"""
    if not is_multi_user_mode():
        # 本地模式从 .env 读取
        return {"configs": [], "message": "本地模式通知配置在系统设置中管理"}
    
    storage = get_storage()
    configs = storage.get_user_notification_configs(user.get("user_id"))
    
    return {"configs": configs}


@router.post("/me/notification-configs")
async def create_my_notification_config(
    data: NotificationConfigCreate,
    request: Request,
    user: dict = Depends(get_current_user_required)
):
    """创建新的通知配置"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式请在系统设置中配置"
        )
    
    storage = get_storage()
    config = storage.save_user_notification_config(user.get("user_id"), data.model_dump())
    
    log_audit_action(user, "create_notification_config", "notification_config", config.get("id"),
                     ip_address=request.client.host if request.client else None)
    
    return {"message": "通知配置创建成功", "config": config}


@router.put("/me/notification-configs/{config_id}")
async def update_my_notification_config(
    config_id: str,
    data: NotificationConfigUpdate,
    request: Request,
    user: dict = Depends(get_current_user_required)
):
    """更新通知配置"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式请在系统设置中配置"
        )

    update_payload = data.model_dump(exclude_none=True)
    if not update_payload:
        return {"message": "配置未变更"}

    update_payload["id"] = config_id
    storage = get_storage()
    existing_configs = storage.get_user_notification_configs(user.get("user_id"))
    if not any(str(item.get("id")) == str(config_id) for item in existing_configs):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    config = storage.save_user_notification_config(user.get("user_id"), update_payload)

    log_audit_action(
        user,
        "update_notification_config",
        "notification_config",
        config_id,
        ip_address=request.client.host if request.client else None,
    )

    return {"message": "通知配置更新成功", "config": config}


@router.delete("/me/notification-configs/{config_id}")
async def delete_my_notification_config(
    config_id: str,
    request: Request,
    user: dict = Depends(get_current_user_required)
):
    """删除通知配置"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式无法删除配置"
        )
    
    storage = get_storage()
    deleted = storage.delete_user_notification_config(config_id, user.get("user_id"))
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    log_audit_action(user, "delete_notification_config", "notification_config", config_id,
                     ip_address=request.client.host if request.client else None)
    
    return {"message": "配置删除成功"}


# ============== 平台账号管理 ==============

@router.get("/me/platform-accounts")
async def get_my_platform_accounts(user: dict = Depends(get_current_user_required)):
    """获取我的平台账号列表"""
    if not is_multi_user_mode():
        # 本地模式从 state 目录读取
        return {"accounts": [], "message": "本地模式平台账号在账号管理页面配置"}
    
    storage = get_storage()
    accounts = storage.get_user_platform_accounts(user.get("user_id"))
    
    # 不返回完整的 cookies
    for account in accounts:
        if "cookies" in account:
            account["has_cookies"] = bool(account["cookies"])
            del account["cookies"]
    
    return {"accounts": accounts}


@router.post("/me/platform-accounts")
async def create_my_platform_account(
    data: PlatformAccountCreate,
    request: Request,
    user: dict = Depends(get_current_user_required)
):
    """创建新的平台账号"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式请在账号管理页面配置"
        )
    
    storage = get_storage()
    account = storage.save_user_platform_account(user.get("user_id"), data.dict())
    
    log_audit_action(user, "create_platform_account", "platform_account", account.get("id"),
                     ip_address=request.client.host if request.client else None)
    
    # 不返回 cookies
    if "cookies" in account:
        del account["cookies"]
    
    return {"message": "平台账号创建成功", "account": account}


@router.put("/me/platform-accounts/{account_id}/cookies")
async def update_platform_account_cookies(
    account_id: str,
    cookies: str,
    request: Request,
    user: dict = Depends(get_current_user_required)
):
    """更新平台账号 Cookies"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式请在账号管理页面配置"
        )
    
    storage = get_storage()
    updated = storage.update_platform_account_cookies(account_id, user.get("user_id"), cookies)
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )
    
    log_audit_action(user, "update_cookies", "platform_account", account_id,
                     ip_address=request.client.host if request.client else None)
    
    return {"message": "Cookies 更新成功"}


@router.delete("/me/platform-accounts/{account_id}")
async def delete_my_platform_account(
    account_id: str,
    request: Request,
    user: dict = Depends(get_current_user_required)
):
    """删除平台账号"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式请在账号管理页面配置"
        )
    
    storage = get_storage()
    deleted = storage.delete_user_platform_account(account_id, user.get("user_id"))
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )
    
    log_audit_action(user, "delete_platform_account", "platform_account", account_id,
                     ip_address=request.client.host if request.client else None)
    
    return {"message": "账号删除成功"}


# ============== 审计日志 ==============

@router.get("/audit-logs")
async def get_audit_logs(
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_admin)
):
    """获取审计日志（管理员）"""
    if not is_multi_user_mode():
        return {"logs": [], "message": "本地模式不记录审计日志"}
    
    storage = get_storage()
    logs = storage.get_audit_logs(
        action=action,
        resource_type=resource_type,
        limit=limit,
        offset=offset
    )
    
    return {"logs": logs}


# ============== 系统信息 ==============

@router.get("/system-info")
async def get_system_info(user: dict = Depends(get_current_user_required)):
    """获取系统信息"""
    categories = sorted(list(get_user_categories(user)))
    management_level = get_user_management_level(user)
    current_role = user.get("role")
    if is_multi_user_mode():
        try:
            storage = get_storage()
            groups = storage.get_user_groups(user.get("user_id"))
            current_role = _infer_legacy_role_from_groups(groups)
        except Exception as e:
            logger.warning(
                "获取当前用户组失败，系统信息回退兼容角色",
                extra={"event": "system_info_group_load_failed", "user_id": user.get("user_id")},
                exc_info=e
            )
    return {
        "is_multi_user_mode": is_multi_user_mode(),
        "storage_backend": STORAGE_BACKEND(),
        "roles": {k: {"level": v["level"], "permissions": v["permissions"]} for k, v in ROLES.items()},
        "current_user_role": current_role,
        "current_user_permissions": [],
        "current_user_management_level": management_level,
        "current_user_categories": categories
    }


@router.get("/me/categories")
async def get_my_categories_api(user: dict = Depends(get_current_user_required)):
    """获取当前用户生效权限类别"""
    categories = sorted(list(get_user_categories(user)))
    return {"categories": categories}


def _extract_result_time_value(result: Dict[str, Any]) -> Optional[str]:
    """从结果记录中提取可展示的时间字段。"""
    candidate_keys = [
        "crawled_at",
        "公开信息浏览时间",
        "crawl_time",
        "发布时间",
    ]
    for key in candidate_keys:
        value = result.get(key)
        if value:
            return str(value)
    product_info = result.get("商品信息") or {}
    if isinstance(product_info, dict):
        publish_time = product_info.get("发布时间")
        if publish_time:
            return str(publish_time)
    return None


@router.get("/me/assets")
async def get_my_assets(user: dict = Depends(get_current_user_required)):
    """获取当前用户资产总览。"""
    storage = get_storage()
    is_multi_mode = is_multi_user_mode()
    user_id = str(user.get("user_id") or user.get("id") or "local_admin")
    owner_id = user_id if is_multi_mode else None

    tasks = storage.get_tasks(owner_id=owner_id)
    task_assets: List[Dict[str, Any]] = []
    results_total = 0

    for task in tasks:
        task_name = task.get("task_name")
        if not task_name:
            continue
        try:
            results = storage.get_results(
                task_name=task_name,
                owner_id=owner_id,
                limit=100000,
                offset=0,
            )
        except Exception as exc:
            logger.warning(
                "读取任务结果失败，已降级为空列表",
                extra={"event": "user_assets_task_results_failed", "user_id": user_id, "task_name": task_name},
                exc_info=exc
            )
            results = []

        result_count = len(results)
        results_total += result_count
        latest_result_time = None
        for result in results:
            time_value = _extract_result_time_value(result)
            if not time_value:
                continue
            if not latest_result_time or str(time_value) > str(latest_result_time):
                latest_result_time = str(time_value)

        task_assets.append({
            "task_name": task_name,
            "keyword": task.get("keyword"),
            "enabled": bool(task.get("enabled", False)),
            "is_running": bool(task.get("is_running", False)),
            "result_count": result_count,
            "latest_result_time": latest_result_time,
        })

    task_assets.sort(key=lambda item: item.get("task_name") or "")

    try:
        accounts = storage.get_user_platform_accounts(user_id)
    except Exception as exc:
        logger.warning(
            "读取用户账号资产失败，已降级为空列表",
            extra={"event": "user_assets_accounts_failed", "user_id": user_id},
            exc_info=exc
        )
        accounts = []

    try:
        api_configs = storage.get_user_api_configs(user_id)
    except Exception as exc:
        logger.warning(
            "读取用户API配置失败，已降级为空列表",
            extra={"event": "user_assets_api_configs_failed", "user_id": user_id},
            exc_info=exc
        )
        api_configs = []

    if not api_configs:
        try:
            default_api_config = storage.get_default_api_config(user_id)
            if default_api_config:
                api_configs = [default_api_config]
        except Exception as exc:
            logger.warning(
                "读取用户默认API配置失败",
                extra={"event": "user_assets_default_api_config_failed", "user_id": user_id},
                exc_info=exc
            )

    try:
        notification_configs = storage.get_user_notification_configs(user_id)
    except Exception as exc:
        logger.warning(
            "读取用户通知配置失败，已降级为空列表",
            extra={"event": "user_assets_notification_configs_failed", "user_id": user_id},
            exc_info=exc
        )
        notification_configs = []

    try:
        ai_criteria = storage.list_ai_criteria(owner_id=owner_id, include_system=False)
    except Exception as exc:
        logger.warning(
            "读取AI标准资产失败，已降级为空列表",
            extra={"event": "user_assets_ai_criteria_failed", "user_id": user_id},
            exc_info=exc
        )
        ai_criteria = []

    try:
        bayes_profiles = storage.list_bayes_profiles(owner_id=owner_id, include_system=False)
    except Exception as exc:
        logger.warning(
            "读取Bayes资产失败，已降级为空列表",
            extra={"event": "user_assets_bayes_profiles_failed", "user_id": user_id},
            exc_info=exc
        )
        bayes_profiles = []

    return {
        "summary": {
            "tasks_total": len(task_assets),
            "results_total": results_total,
            "accounts_total": len(accounts),
            "api_configs_total": len(api_configs),
            "notification_configs_total": len(notification_configs),
            "ai_criteria_total": len(ai_criteria),
            "bayes_profiles_total": len(bayes_profiles),
        },
        "task_assets": task_assets,
        "accounts": [
            {
                "id": item.get("id"),
                "display_name": item.get("display_name") or item.get("name") or item.get("id"),
                "is_active": bool(item.get("is_active", False)),
                "risk_control_count": int(item.get("risk_control_count") or 0),
                "last_used_at": item.get("last_used_at"),
                "created_at": item.get("created_at"),
            }
            for item in accounts
        ],
        "api_configs": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "provider": item.get("provider"),
                "model": item.get("model"),
                "is_default": bool(item.get("is_default", False)),
            }
            for item in api_configs
        ],
        "notification_configs": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "channel_type": item.get("channel_type"),
                "is_enabled": bool(item.get("is_enabled", False)),
            }
            for item in notification_configs
        ],
        "generated_at": datetime.now().isoformat(),
    }


# ============== 用户组管理 ==============

@groups_router.get("")
@router.get("/groups")
async def list_user_groups_api(user: dict = Depends(require_admin)):
    """获取用户组列表（管理员）"""
    if not is_multi_user_mode():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="本地模式不支持用户组管理")
    storage = get_storage()
    groups = storage.list_user_groups()
    return {"groups": groups}


@groups_router.post("")
@router.post("/groups")
async def create_user_group_api(
    data: UserGroupCreate,
    request: Request,
    user: dict = Depends(require_admin)
):
    """创建用户组（管理员）"""
    if not is_multi_user_mode():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="本地模式不支持用户组管理")

    storage = get_storage()
    payload = data.dict()
    payload["created_by"] = user.get("user_id")
    try:
        created = storage.create_user_group(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    log_audit_action(
        user,
        "create_user_group",
        "group",
        resource_id=created.get("id"),
        details={"code": created.get("code"), "name": created.get("name")},
        ip_address=request.client.host if request.client else None
    )
    return {"message": "用户组创建成功", "group": created}


@groups_router.put("/{group_id}")
@router.put("/groups/{group_id}")
async def update_user_group_api(
    group_id: str,
    data: UserGroupUpdate,
    request: Request,
    user: dict = Depends(require_admin)
):
    """更新用户组（管理员）"""
    if not is_multi_user_mode():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="本地模式不支持用户组管理")

    storage = get_storage()
    payload = {k: v for k, v in data.dict().items() if v is not None}
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无更新内容")
    try:
        updated = storage.update_user_group(group_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户组不存在")

    log_audit_action(
        user,
        "update_user_group",
        "group",
        resource_id=group_id,
        details=payload,
        ip_address=request.client.host if request.client else None
    )
    return {"message": "用户组更新成功", "group": updated}


@groups_router.delete("/{group_id}")
@router.delete("/groups/{group_id}")
async def delete_user_group_api(
    group_id: str,
    request: Request,
    user: dict = Depends(require_admin)
):
    """删除用户组（管理员）"""
    if not is_multi_user_mode():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="本地模式不支持用户组管理")

    storage = get_storage()
    try:
        deleted = storage.delete_user_group(group_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户组不存在")

    log_audit_action(
        user,
        "delete_user_group",
        "group",
        resource_id=group_id,
        ip_address=request.client.host if request.client else None
    )
    return {"message": "用户组删除成功"}


@groups_router.get("/{group_id}/permissions")
@router.get("/groups/{group_id}/permissions")
async def get_group_permissions_api(group_id: str, user: dict = Depends(require_admin)):
    """获取用户组权限（管理员）"""
    if not is_multi_user_mode():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="本地模式不支持用户组管理")
    storage = get_storage()
    permissions = storage.get_group_permissions(group_id)
    if permissions == [] and not storage.get_user_group(group_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户组不存在")
    return {"permissions": permissions}


@groups_router.put("/{group_id}/permissions")
@router.put("/groups/{group_id}/permissions")
async def set_group_permissions_api(
    group_id: str,
    data: GroupPermissionUpdate,
    request: Request,
    user: dict = Depends(require_admin)
):
    """设置用户组权限（管理员）"""
    if not is_multi_user_mode():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="本地模式不支持用户组管理")

    storage = get_storage()
    current_group = storage.get_user_group(group_id)
    ensure_group_permission_edit_scope(user, current_group)
    updated = storage.set_group_permissions(group_id, data.categories)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户组不存在")

    log_audit_action(
        user,
        "set_group_permissions",
        "group",
        resource_id=group_id,
        details={"categories": data.categories},
        ip_address=request.client.host if request.client else None
    )
    return {"message": "用户组权限更新成功"}


@router.put("/{user_id}/groups")
async def set_user_groups_api(
    user_id: str,
    data: UserGroupAssignment,
    request: Request,
    user: dict = Depends(require_admin)
):
    """覆盖设置指定用户所属组（管理员）"""
    if not is_multi_user_mode():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="本地模式不支持用户组管理")
    storage = get_storage()
    target_user = storage.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if len(data.group_ids) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少分配一个用户组")
    ensure_admin_scope(user, storage=storage, target_user=target_user, target_group_ids=data.group_ids)
    try:
        updated = storage.set_user_groups(user_id, data.group_ids)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="更新用户组失败")

    log_audit_action(
        user,
        "set_user_groups",
        "user",
        resource_id=user_id,
        details={"group_ids": data.group_ids},
        ip_address=request.client.host if request.client else None
    )
    groups = storage.get_user_groups(user_id)
    return {
        "message": "用户组分配成功",
        "groups": [{"id": group.get("id"), "code": group.get("code"), "name": group.get("name")} for group in groups],
        "role": _infer_legacy_role_from_groups(groups)
    }


# ============== 页面权限 ==============

@router.get("/page-permissions")
async def get_page_permissions_api(user: dict = Depends(get_current_user_required)):
    """获取页面权限配置"""
    user_role = user.get("role", "viewer")
    if is_multi_user_mode():
        try:
            storage = get_storage()
            current_groups = storage.get_user_groups(user.get("user_id"))
            user_role = _infer_legacy_role_from_groups(current_groups)
        except Exception:
            pass
    page_keys = set(PAGE_PERMISSIONS.keys())
    page_keys.update({"user-data"})
    accessible_pages = {page: can_access_page(user, page) for page in sorted(page_keys)}
    categories = sorted(list(get_user_categories(user)))
    return {
        "role": user_role,
        "permissions": PAGE_PERMISSIONS,
        "accessible_pages": accessible_pages,
        "categories": categories
    }


# ============== RBAC 配置管理 ==============

@router.get("/rbac-config")
async def get_rbac_config_api(user: dict = Depends(require_admin)):
    """获取 RBAC 配置（高级只读视图）"""
    rbac_config = get_rbac_config()
    current_role = user.get("role", "viewer")
    if is_multi_user_mode():
        try:
            storage = get_storage()
            groups = storage.get_user_groups(user.get("user_id"))
            current_role = _infer_legacy_role_from_groups(groups)
        except Exception as e:
            logger.warning(
                "获取当前用户组失败，RBAC视图回退兼容角色",
                extra={"event": "rbac_view_group_load_failed", "user_id": user.get("user_id")},
                exc_info=e
            )
    return {
        "roles": rbac_config.get("roles", {}),
        "page_permissions": rbac_config.get("page_permissions", {}),
        "available_permissions": get_available_permissions(rbac_config.get("roles", {})),
        "current_role": current_role,
        "read_only": True
    }


@router.put("/rbac-config")
async def update_rbac_config_api(
    data: RbacConfigUpdate,
    request: Request,
    user: dict = Depends(require_admin)
):
    """禁用旧 RBAC 写入，避免与用户组模型冲突"""
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="RBAC 写入已禁用，请使用用户组管理功能进行权限配置"
    )


# ============== 个人资料管理 ==============

@router.put("/me/profile")
async def update_my_profile(
    data: ProfileUpdate,
    request: Request,
    user: dict = Depends(get_current_user_required)
):
    """更新个人资料（邮箱）"""
    if not is_multi_user_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本地模式请直接修改 .env 文件"
        )
    
    storage = get_storage()
    updates = {k: v for k, v in data.dict().items() if v is not None}
    
    if not updates:
        return {"message": "无更新内容"}
    
    updated = storage.update_user(user.get("user_id"), updates)
    
    log_audit_action(user, "update_profile", "user", user.get("user_id"),
                     details=updates,
                     ip_address=request.client.host if request.client else None)
    
    return {"message": "资料更新成功", "user": updated}


# 头像存储目录
AVATAR_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "static", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

# 头像大小限制
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB
AVATAR_DIMENSION = 200  # 压缩后尺寸


@router.post("/me/avatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user_required)
):
    """
    上传用户头像
    - 限制大小：2MB
    - 自动压缩：200x200
    - 支持格式：jpg, png, gif, webp
    """
    # 验证文件类型
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的图片格式，仅支持: {', '.join(allowed_types)}"
        )
    
    # 读取文件内容
    contents = await file.read()
    
    # 验证文件大小
    if len(contents) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件过大，最大允许 {MAX_AVATAR_SIZE // 1024 // 1024}MB"
        )
    
    try:
        # 使用 PIL 处理图片
        img = Image.open(io.BytesIO(contents))
        
        # 转换为 RGB（处理 RGBA 和其他模式）
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # 裁剪为正方形（居中）
        width, height = img.size
        min_dim = min(width, height)
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        img = img.crop((left, top, left + min_dim, top + min_dim))
        
        # 压缩到目标尺寸
        img = img.resize((AVATAR_DIMENSION, AVATAR_DIMENSION), Image.LANCZOS)
        
        # 保存到文件
        user_id = user.get("user_id", "unknown")
        filename = f"{user_id}.jpg"
        filepath = os.path.join(AVATAR_DIR, filename)
        
        img.save(filepath, "JPEG", quality=85, optimize=True)
        
        # 返回头像 URL
        avatar_url = f"/static/avatars/{filename}?t={int(datetime.now().timestamp())}"
        
        # 如果是多用户模式，更新数据库
        if is_multi_user_mode():
            storage = get_storage()
            storage.update_user(user.get("user_id"), {"avatar_url": avatar_url})
        
        log_audit_action(user, "upload_avatar", "user", user.get("user_id"),
                         ip_address=request.client.host if request.client else None)
        
        return {"message": "头像上传成功", "avatar_url": avatar_url}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"图片处理失败: {str(e)}"
        )


@router.get("/me/avatar")
async def get_my_avatar(user: dict = Depends(get_current_user_required)):
    """获取当前用户头像 URL"""
    user_id = user.get("user_id", "unknown")
    filename = f"{user_id}.jpg"
    filepath = os.path.join(AVATAR_DIR, filename)
    
    if os.path.exists(filepath):
        avatar_url = f"/static/avatars/{filename}?t={int(os.path.getmtime(filepath))}"
        return {"avatar_url": avatar_url}
    
    # 返回默认头像（首字母）
    return {"avatar_url": None, "default_initial": user.get("username", "U")[0].upper()}

