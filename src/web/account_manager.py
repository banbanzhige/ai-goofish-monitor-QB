"""
账号管理模块 - 统一支持本地模式与多用户模式
"""
import os
import re
import json
import aiofiles
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.storage import get_storage
from src.web.auth import get_current_user, is_multi_user_mode
from src.logging_config import get_logger


router = APIRouter()
logger = get_logger(__name__, service="web")

STATE_DIR = "state"
ACTIVE_ACCOUNT_FILE = os.path.join(STATE_DIR, "_active.json")
SYSTEM_ACCOUNT_FIELDS = {
    "display_name",
    "created_at",
    "last_used_at",
    "risk_control_count",
    "risk_control_history",
    "order",
    "cookie_status",
}
REQUIRED_COOKIES = ["_m_h5_tk", "_m_h5_tk_enc", "cookie2"]


class AccountInfo(BaseModel):
    name: str
    display_name: str
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None
    is_active: bool = False
    risk_control_count: int = 0
    cookie_status: Optional[str] = None
    order: Optional[int] = None


class AccountCreate(BaseModel):
    name: str
    display_name: str
    state_content: str


class AccountUpdate(BaseModel):
    display_name: Optional[str] = None
    state_content: Optional[str] = None


class AccountOrderUpdate(BaseModel):
    ordered_names: List[str]


class RiskControlRecord(BaseModel):
    timestamp: str
    reason: str
    task_name: Optional[str] = None


class DuplicateAccountRequest(BaseModel):
    new_name: Optional[str] = None


def _get_current_user_id(request: Optional[Request]) -> Optional[str]:
    if not is_multi_user_mode() or request is None:
        return None
    user = get_current_user(request)
    if not user:
        return None
    user_id = user.get("user_id") or user.get("id")
    return str(user_id) if user_id else None


def ensure_state_dir():
    os.makedirs(STATE_DIR, exist_ok=True)


def _is_account_expired(cookies: list, current_time: float) -> bool:
    if not cookies:
        return True
    for cookie in cookies:
        expires = cookie.get("expires", 0)
        if expires > 0 and expires < current_time:
            return True
    return False


def _merge_state_payload(target: dict, state_data):
    if isinstance(state_data, dict):
        for key, value in state_data.items():
            if key in SYSTEM_ACCOUNT_FIELDS:
                continue
            target[key] = value
    elif isinstance(state_data, list):
        target["cookies"] = state_data


def _extract_cookies_from_state_content(state_content: str) -> Tuple[List[Dict[str, Any]], str]:
    try:
        state_data = json.loads(state_content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Cookie内容不是有效的JSON格式")

    cookies: List[Dict[str, Any]] = []
    if isinstance(state_data, list):
        cookies = state_data
    elif isinstance(state_data, dict):
        cookies = state_data.get("cookies", []) if isinstance(state_data.get("cookies", []), list) else []
    cookies_json = json.dumps(cookies, ensure_ascii=False)
    return cookies, cookies_json


def _parse_cookies(raw_cookies: Any) -> List[Dict[str, Any]]:
    if raw_cookies is None:
        return []
    if isinstance(raw_cookies, list):
        return raw_cookies
    if isinstance(raw_cookies, str):
        try:
            loaded = json.loads(raw_cookies)
            if isinstance(loaded, list):
                return loaded
            if isinstance(loaded, dict):
                return loaded.get("cookies", []) if isinstance(loaded.get("cookies", []), list) else []
        except Exception:
            return []
    if isinstance(raw_cookies, dict):
        value = raw_cookies.get("cookies", [])
        return value if isinstance(value, list) else []
    return []


def _detect_cookie_status(cookies: List[Dict[str, Any]]) -> str:
    import time

    current_time = time.time()
    if not cookies:
        return "expired"
    return "expired" if _is_account_expired(cookies, current_time) else "valid"


def _map_storage_account_to_info(account: Dict[str, Any], index: int) -> AccountInfo:
    cookies = _parse_cookies(account.get("cookies"))
    return AccountInfo(
        name=str(account.get("id")),
        display_name=account.get("display_name") or f"账号{index + 1}",
        created_at=account.get("created_at"),
        last_used_at=account.get("last_used_at"),
        is_active=bool(account.get("is_active", False)),
        risk_control_count=int(account.get("risk_control_count") or 0),
        cookie_status=_detect_cookie_status(cookies),
        order=index,
    )


def _find_storage_account(accounts: List[Dict[str, Any]], account_id: str) -> Optional[Dict[str, Any]]:
    for account in accounts:
        if str(account.get("id")) == str(account_id):
            return account
    return None


async def _set_storage_active_account(user_id: str, target_account_id: str):
    storage = get_storage()
    accounts = storage.get_user_platform_accounts(user_id)
    for account in accounts:
        account["is_active"] = str(account.get("id")) == str(target_account_id)
        storage.save_user_platform_account(user_id, account)


def get_account_file_path(name: str) -> str:
    if "/" in name or "\\" in name or ".." in name:
        raise ValueError("无效的账号名")
    return os.path.join(STATE_DIR, f"{name}.json")


async def read_account_file(name: str) -> dict:
    filepath = get_account_file_path(name)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"账号 '{name}' 不存在")
    async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
        return json.loads(await f.read())


async def write_account_file(name: str, data: dict):
    ensure_state_dir()
    filepath = get_account_file_path(name)
    async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=2))


async def get_active_account_name() -> Optional[str]:
    if not os.path.exists(ACTIVE_ACCOUNT_FILE):
        return None
    try:
        async with aiofiles.open(ACTIVE_ACCOUNT_FILE, 'r', encoding='utf-8') as f:
            data = json.loads(await f.read())
        return data.get("active_account")
    except Exception:
        return None


async def set_active_account_name(name: str):
    ensure_state_dir()
    async with aiofiles.open(ACTIVE_ACCOUNT_FILE, 'w', encoding='utf-8') as f:
        await f.write(json.dumps({"active_account": name}, ensure_ascii=False))


def _build_local_state_content(data: Dict[str, Any]) -> Optional[str]:
    try:
        state_data = {
            "cookies": data.get("cookies", []),
            "env": data.get("env"),
            "headers": data.get("headers"),
            "page": data.get("page"),
            "storage": data.get("storage"),
        }
        return json.dumps(state_data, ensure_ascii=False, indent=2)
    except Exception:
        return None


@router.get("/api/accounts")
async def list_accounts(request: Request) -> List[AccountInfo]:
    """获取账号列表"""
    user_id = _get_current_user_id(request)
    if user_id:
        storage = get_storage()
        accounts = storage.get_user_platform_accounts(user_id)
        accounts.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return [_map_storage_account_to_info(account, idx) for idx, account in enumerate(accounts)]

    ensure_state_dir()
    accounts: List[AccountInfo] = []
    active_account = await get_active_account_name()

    import time
    current_time = time.time()

    for filename in os.listdir(STATE_DIR):
        if filename.endswith(".json") and not filename.startswith("_"):
            name = filename[:-5]
            try:
                data = await read_account_file(name)
                cookie_status = data.get("cookie_status", "unknown")
                if cookie_status == "unknown":
                    cookies = data.get("cookies", [])
                    cookie_status = "expired" if _is_account_expired(cookies, current_time) else "valid"
                accounts.append(AccountInfo(
                    name=name,
                    display_name=data.get("display_name", name),
                    created_at=data.get("created_at"),
                    last_used_at=data.get("last_used_at"),
                    is_active=(name == active_account),
                    risk_control_count=data.get("risk_control_count", 0),
                    cookie_status=cookie_status,
                    order=data.get("order"),
                ))
            except Exception as e:
                logger.warning(f"读取账号文件失败: {filename}, 错误: {e}", extra={"event": "account_file_read_failed"})

    has_order = any(account.order is not None for account in accounts)
    if has_order:
        accounts.sort(key=lambda x: (x.order is None, x.order if x.order is not None else 0, x.created_at or ""))
    else:
        accounts.sort(key=lambda x: x.created_at or "", reverse=True)
    return accounts


@router.post("/api/accounts/reorder")
async def reorder_accounts(payload: AccountOrderUpdate, request: Request):
    """更新账号排序"""
    user_id = _get_current_user_id(request)
    if user_id:
        # 多用户模式下账户存储在数据库，当前仅做接口兼容和参数校验。
        storage = get_storage()
        existing = storage.get_user_platform_accounts(user_id)
        existing_ids = {str(item.get("id")) for item in existing}
        ordered_ids = [str(name) for name in payload.ordered_names]
        if len(existing_ids) != len(ordered_ids):
            raise HTTPException(status_code=400, detail="排序账号数量不匹配")
        if set(ordered_ids) != existing_ids:
            raise HTTPException(status_code=400, detail="排序列表与现有账号不一致")
        return {"message": "账号排序更新成功"}

    ordered_names = payload.ordered_names
    ensure_state_dir()

    existing_names = [
        filename[:-5]
        for filename in os.listdir(STATE_DIR)
        if filename.endswith(".json") and not filename.startswith("_")
    ]

    if len(ordered_names) != len(existing_names):
        raise HTTPException(status_code=400, detail="排序账号数量不匹配")

    if len(set(ordered_names)) != len(ordered_names):
        raise HTTPException(status_code=400, detail="排序列表包含重复账号")

    missing = [name for name in ordered_names if name not in existing_names]
    if missing:
        raise HTTPException(status_code=400, detail=f"排序列表缺少账号: {missing}")

    for idx, name in enumerate(ordered_names):
        data = await read_account_file(name)
        data["order"] = idx
        await write_account_file(name, data)

    return {"message": "账号排序更新成功"}


@router.post("/api/accounts/cleanup-expired")
async def cleanup_expired_accounts(request: Request):
    """批量清理失效账号"""
    user_id = _get_current_user_id(request)
    if user_id:
        storage = get_storage()
        accounts = storage.get_user_platform_accounts(user_id)
        deleted_names: List[str] = []
        import time
        current_time = time.time()

        for account in accounts:
            cookies = _parse_cookies(account.get("cookies"))
            if _is_account_expired(cookies, current_time):
                account_id = str(account.get("id"))
                storage.delete_user_platform_account(account_id, user_id)
                deleted_names.append(account.get("display_name") or account_id)

        if not deleted_names:
            return {"message": "未发现可清理的失效账号", "deleted": [], "count": 0}
        return {"message": f"已清理 {len(deleted_names)} 个失效账号", "deleted": deleted_names, "count": len(deleted_names)}

    ensure_state_dir()
    import time
    import asyncio

    current_time = time.time()
    active_account = await get_active_account_name()
    deleted_names: List[str] = []

    for filename in os.listdir(STATE_DIR):
        if not filename.endswith(".json") or filename.startswith("_"):
            continue
        name = filename[:-5]
        filepath = get_account_file_path(name)
        try:
            data = await read_account_file(name)
        except Exception:
            continue

        cookies = data.get("cookies", [])
        if not _is_account_expired(cookies, current_time):
            continue

        try:
            removed = False
            for attempt in range(3):
                try:
                    os.remove(filepath)
                    removed = True
                    break
                except PermissionError:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(0.05)
            if not removed:
                continue
            deleted_names.append(name)
            if name == active_account and os.path.exists(ACTIVE_ACCOUNT_FILE):
                os.remove(ACTIVE_ACCOUNT_FILE)
        except FileNotFoundError:
            continue
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"清理失效账号失败: {e}")

    if not deleted_names:
        return {"message": "未发现可清理的失效账号", "deleted": [], "count": 0}
    return {"message": f"已清理 {len(deleted_names)} 个失效账号", "deleted": deleted_names, "count": len(deleted_names)}


@router.post("/api/accounts")
async def create_account(account: AccountCreate, request: Request):
    """创建新账号"""
    user_id = _get_current_user_id(request)
    cookies, cookies_json = _extract_cookies_from_state_content(account.state_content)

    if user_id:
        storage = get_storage()
        created = storage.save_user_platform_account(user_id, {
            "platform": "goofish",
            "display_name": account.display_name or account.name,
            "cookies": cookies_json,
            "risk_control_count": 0,
            "risk_control_history": [],
            "is_active": False,
        })
        accounts = storage.get_user_platform_accounts(user_id)
        if len(accounts) == 1:
            await _set_storage_active_account(user_id, str(created.get("id")))
        return {"message": f"账号 '{account.display_name or account.name}' 创建成功"}

    ensure_state_dir()
    filepath = get_account_file_path(account.name)
    if os.path.exists(filepath):
        raise HTTPException(status_code=400, detail=f"账号 '{account.name}' 已存在")

    account_data = {
        "display_name": account.display_name,
        "created_at": datetime.now().isoformat(),
        "last_used_at": None,
        "risk_control_count": 0,
        "risk_control_history": [],
    }

    _merge_state_payload(account_data, cookies)

    existing_orders = []
    for filename in os.listdir(STATE_DIR):
        if filename.endswith(".json") and not filename.startswith("_"):
            name = filename[:-5]
            try:
                data = await read_account_file(name)
                order_value = data.get("order")
                if isinstance(order_value, int):
                    existing_orders.append(order_value)
            except Exception:
                continue

    account_data["order"] = (max(existing_orders) + 1) if existing_orders else 0
    await write_account_file(account.name, account_data)

    accounts = await list_accounts(request)
    if len(accounts) == 1:
        await set_active_account_name(account.name)

    return {"message": f"账号 '{account.display_name}' 创建成功"}


@router.get("/api/accounts/{name}")
async def get_account(name: str, request: Request):
    """获取账号详情"""
    user_id = _get_current_user_id(request)
    if user_id:
        storage = get_storage()
        accounts = storage.get_user_platform_accounts(user_id)
        account = _find_storage_account(accounts, name)
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")

        cookies = _parse_cookies(account.get("cookies"))
        state_content = json.dumps({"cookies": cookies}, ensure_ascii=False, indent=2)
        return {
            "name": str(account.get("id")),
            "display_name": account.get("display_name") or str(account.get("id")),
            "created_at": account.get("created_at"),
            "last_used_at": account.get("last_used_at"),
            "is_active": bool(account.get("is_active", False)),
            "risk_control_count": int(account.get("risk_control_count") or 0),
            "risk_control_history": account.get("risk_control_history") or [],
            "state_content": state_content,
        }

    data = await read_account_file(name)
    active_account = await get_active_account_name()
    return {
        "name": name,
        "display_name": data.get("display_name", name),
        "created_at": data.get("created_at"),
        "last_used_at": data.get("last_used_at"),
        "is_active": (name == active_account),
        "risk_control_count": data.get("risk_control_count", 0),
        "risk_control_history": data.get("risk_control_history", []),
        "state_content": _build_local_state_content(data),
    }


@router.post("/api/accounts/{name}/test")
async def test_account_cookie(name: str, request: Request):
    """测试账号Cookie有效性"""
    user_id = _get_current_user_id(request)

    if user_id:
        storage = get_storage()
        accounts = storage.get_user_platform_accounts(user_id)
        account = _find_storage_account(accounts, name)
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")
        cookies = _parse_cookies(account.get("cookies"))
    else:
        data = await read_account_file(name)
        cookies = data.get("cookies", [])

    if not cookies:
        return {"valid": False, "message": f"账号 '{name}' 没有Cookie数据"}

    import time
    current_time = time.time()
    found_cookies = set()
    expired_cookies = []

    for cookie in cookies:
        cookie_name = cookie.get("name", "")
        if cookie_name in REQUIRED_COOKIES:
            found_cookies.add(cookie_name)
            expires = cookie.get("expires", 0)
            if expires > 0 and expires < current_time:
                expired_cookies.append(cookie_name)

    if expired_cookies:
        return {"valid": False, "message": f"账号 '{name}' 的以下Cookie已过期: {', '.join(expired_cookies)}"}

    missing = set(REQUIRED_COOKIES) - found_cookies
    if missing:
        return {"valid": False, "message": f"账号 '{name}' 缺少关键Cookie: {', '.join(missing)}"}

    return {"valid": True, "message": f"账号 '{name}' 的Cookie看起来有效"}


def generate_unique_account_name(base_name: str) -> str:
    ensure_state_dir()
    clean_name = re.sub(r"（副本\d+）", "", base_name)

    existing_names = set()
    for filename in os.listdir(STATE_DIR):
        if filename.endswith(".json") and not filename.startswith("_"):
            existing_names.add(filename[:-5])

    for i in range(1, 1000):
        new_name = f"{clean_name}（副本{i}）"
        if new_name not in existing_names:
            return new_name

    return f"{clean_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"


@router.post("/api/accounts/{name}/duplicate")
async def duplicate_account(name: str, request: Request, payload: DuplicateAccountRequest = None):
    """复制账号"""
    user_id = _get_current_user_id(request)

    if user_id:
        storage = get_storage()
        accounts = storage.get_user_platform_accounts(user_id)
        source = _find_storage_account(accounts, name)
        if not source:
            raise HTTPException(status_code=404, detail="源账号不存在")

        target_name = payload.new_name if payload and payload.new_name else None
        if not target_name:
            base_name = source.get("display_name") or "账号副本"
            existing_display_names = {str(item.get("display_name") or "") for item in accounts}
            counter = 1
            target_name = f"{base_name}（副本{counter}）"
            while target_name in existing_display_names:
                counter += 1
                target_name = f"{base_name}（副本{counter}）"

        copied = dict(source)
        copied.pop("id", None)
        copied["display_name"] = target_name
        copied["created_at"] = datetime.now().isoformat()
        copied["last_used_at"] = None
        copied["risk_control_count"] = 0
        copied["risk_control_history"] = []
        copied["is_active"] = False
        storage.save_user_platform_account(user_id, copied)
        return {"message": f"账号 '{name}' 已成功复制为 '{target_name}'", "new_name": target_name}

    source_data = await read_account_file(name)
    if payload and payload.new_name:
        new_name = payload.new_name
        new_filepath = get_account_file_path(new_name)
        if os.path.exists(new_filepath):
            new_name = generate_unique_account_name(new_name)
    else:
        base_display_name = source_data.get("display_name", name)
        new_name = generate_unique_account_name(base_display_name)

    new_data = source_data.copy()
    new_data["display_name"] = new_name
    new_data["created_at"] = datetime.now().isoformat()
    new_data["last_used_at"] = None
    new_data["risk_control_count"] = 0
    new_data["risk_control_history"] = []

    await write_account_file(new_name, new_data)
    return {"message": f"账号 '{name}' 已成功复制为 '{new_name}'", "new_name": new_name}


@router.put("/api/accounts/{name}")
async def update_account(name: str, update: AccountUpdate, request: Request):
    """更新账号信息"""
    user_id = _get_current_user_id(request)

    if user_id:
        storage = get_storage()
        accounts = storage.get_user_platform_accounts(user_id)
        account = _find_storage_account(accounts, name)
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")

        payload: Dict[str, Any] = {"id": account.get("id")}
        if update.display_name is not None:
            payload["display_name"] = update.display_name
        if update.state_content is not None:
            _, cookies_json = _extract_cookies_from_state_content(update.state_content)
            payload["cookies"] = cookies_json

        merged = dict(account)
        merged.update(payload)
        storage.save_user_platform_account(user_id, merged)
        return {"message": f"账号 '{name}' 更新成功"}

    data = await read_account_file(name)

    if update.display_name is not None:
        data["display_name"] = update.display_name

    if update.state_content is not None:
        state_data = json.loads(update.state_content)
        _merge_state_payload(data, state_data)

    await write_account_file(name, data)
    return {"message": f"账号 '{name}' 更新成功"}


@router.delete("/api/accounts/{name}")
async def delete_account(name: str, request: Request):
    """删除账号"""
    user_id = _get_current_user_id(request)

    if user_id:
        storage = get_storage()
        deleted = storage.delete_user_platform_account(name, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="账号不存在")
        return {"message": f"账号 '{name}' 已删除"}

    filepath = get_account_file_path(name)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"账号 '{name}' 不存在")

    active_account = await get_active_account_name()
    if name == active_account and os.path.exists(ACTIVE_ACCOUNT_FILE):
        os.remove(ACTIVE_ACCOUNT_FILE)

    os.remove(filepath)
    return {"message": f"账号 '{name}' 已删除"}


@router.post("/api/accounts/{name}/activate")
async def activate_account(name: str, request: Request):
    """激活账号"""
    user_id = _get_current_user_id(request)
    if user_id:
        storage = get_storage()
        accounts = storage.get_user_platform_accounts(user_id)
        account = _find_storage_account(accounts, name)
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")
        await _set_storage_active_account(user_id, name)
        return {"message": f"账号 '{name}' 已激活"}

    filepath = get_account_file_path(name)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"账号 '{name}' 不存在")

    await set_active_account_name(name)
    return {"message": f"账号 '{name}' 已激活"}


@router.post("/api/accounts/{name}/record-risk-control")
async def record_risk_control(name: str, request: Request, reason: str = "未知原因", task_name: str = None):
    """记录风控触发"""
    user_id = _get_current_user_id(request)

    if user_id:
        storage = get_storage()
        accounts = storage.get_user_platform_accounts(user_id)
        account = _find_storage_account(accounts, name)
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")

        history = account.get("risk_control_history") or []
        history.append({"timestamp": datetime.now().isoformat(), "reason": reason, "task_name": task_name})
        history = history[-50:]
        account["risk_control_count"] = int(account.get("risk_control_count") or 0) + 1
        account["risk_control_history"] = history
        storage.save_user_platform_account(user_id, account)
        return {"message": "风控记录已保存"}

    data = await read_account_file(name)
    data["risk_control_count"] = data.get("risk_control_count", 0) + 1
    if "risk_control_history" not in data:
        data["risk_control_history"] = []

    data["risk_control_history"].append({
        "timestamp": datetime.now().isoformat(),
        "reason": reason,
        "task_name": task_name,
    })
    data["risk_control_history"] = data["risk_control_history"][-50:]
    await write_account_file(name, data)
    return {"message": "风控记录已保存"}


@router.post("/api/accounts/{name}/update-last-used")
async def update_last_used(name: str, request: Request):
    """更新最后使用时间"""
    user_id = _get_current_user_id(request)

    if user_id:
        storage = get_storage()
        accounts = storage.get_user_platform_accounts(user_id)
        account = _find_storage_account(accounts, name)
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")
        account["last_used_at"] = datetime.now().isoformat()
        storage.save_user_platform_account(user_id, account)
        return {"message": "使用时间已更新"}

    data = await read_account_file(name)
    data["last_used_at"] = datetime.now().isoformat()
    await write_account_file(name, data)
    return {"message": "使用时间已更新"}


async def get_account_state_for_scraper(name: str, user_id: Optional[str] = None) -> dict:
    """获取账号状态供采集器使用"""
    if user_id and is_multi_user_mode():
        storage = get_storage()
        accounts = storage.get_user_platform_accounts(user_id)
        account = _find_storage_account(accounts, name)
        if not account:
            raise HTTPException(status_code=404, detail=f"账号 '{name}' 不存在")

        account["last_used_at"] = datetime.now().isoformat()
        storage.save_user_platform_account(user_id, account)
        return {"cookies": _parse_cookies(account.get("cookies")), "env": None, "headers": None, "page": None, "storage": None}

    data = await read_account_file(name)
    data["last_used_at"] = datetime.now().isoformat()
    await write_account_file(name, data)
    return {
        "cookies": data.get("cookies", []),
        "env": data.get("env"),
        "headers": data.get("headers"),
        "page": data.get("page"),
        "storage": data.get("storage"),
    }


async def get_next_available_account(current_account: str, user_id: Optional[str] = None) -> Optional[str]:
    """获取下一个可用账号"""
    if user_id and is_multi_user_mode():
        storage = get_storage()
        accounts = storage.get_user_platform_accounts(user_id)
        available = [item for item in accounts if str(item.get("id")) != str(current_account)]
        if not available:
            return None
        available.sort(key=lambda item: int(item.get("risk_control_count") or 0))
        return str(available[0].get("id"))

    ensure_state_dir()
    active_list: List[AccountInfo] = []
    active_account = await get_active_account_name()
    import time
    current_time = time.time()
    for filename in os.listdir(STATE_DIR):
        if not filename.endswith(".json") or filename.startswith("_"):
            continue
        name = filename[:-5]
        try:
            data = await read_account_file(name)
            active_list.append(AccountInfo(
                name=name,
                display_name=data.get("display_name", name),
                created_at=data.get("created_at"),
                last_used_at=data.get("last_used_at"),
                is_active=(name == active_account),
                risk_control_count=data.get("risk_control_count", 0),
                cookie_status="expired" if _is_account_expired(data.get("cookies", []), current_time) else "valid",
                order=data.get("order"),
            ))
        except Exception:
            continue

    available = [a for a in active_list if a.name != current_account]
    if not available:
        return None
    available.sort(key=lambda x: x.risk_control_count)
    return available[0].name
