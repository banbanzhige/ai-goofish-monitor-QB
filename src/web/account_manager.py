"""
账号管理模块 - 管理咸鱼Cookie账号
存储在 state/ 目录下
"""
import os
import json
import aiofiles
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter()
STATE_DIR = "state"
ACTIVE_ACCOUNT_FILE = os.path.join(STATE_DIR, "_active.json")


# ============== 数据模型 ==============

class AccountInfo(BaseModel):
    """账号信息模型"""
    name: str
    display_name: str
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None
    is_active: bool = False
    risk_control_count: int = 0
    cookie_status: Optional[str] = None  # valid, expired, unknown
    order: Optional[int] = None


class AccountCreate(BaseModel):
    """创建账号请求"""
    name: str
    display_name: str
    state_content: str  # 浏览器扩展导出的JSON字符串


class AccountUpdate(BaseModel):
    """更新账号请求"""
    display_name: Optional[str] = None
    state_content: Optional[str] = None


class AccountOrderUpdate(BaseModel):
    """更新账号请求"""
    ordered_names: List[str]


class RiskControlRecord(BaseModel):
    """风控记录"""
    timestamp: str
    reason: str
    task_name: Optional[str] = None


# ============== 辅助函数 ==============

def ensure_state_dir():
    """确保state目录存在"""
    os.makedirs(STATE_DIR, exist_ok=True)


def get_account_file_path(name: str) -> str:
    """获取账号文件路径"""
    # 安全检查：防止路径遍历
    if "/" in name or "\\" in name or ".." in name:
        raise ValueError("无效的账号名")
    return os.path.join(STATE_DIR, f"{name}.json")


async def read_account_file(name: str) -> dict:
    """读取账号文件"""
    filepath = get_account_file_path(name)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"账号 '{name}' 不存在")
    
    async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
        content = await f.read()
    return json.loads(content)


async def write_account_file(name: str, data: dict):
    """写入账号文件"""
    ensure_state_dir()
    filepath = get_account_file_path(name)
    async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=2))


async def get_active_account_name() -> Optional[str]:
    """获取当前激活的账号名"""
    if not os.path.exists(ACTIVE_ACCOUNT_FILE):
        return None
    try:
        async with aiofiles.open(ACTIVE_ACCOUNT_FILE, 'r', encoding='utf-8') as f:
            content = await f.read()
        data = json.loads(content)
        return data.get("active_account")
    except Exception:
        return None


async def set_active_account_name(name: str):
    """设置当前激活的账号"""
    ensure_state_dir()
    async with aiofiles.open(ACTIVE_ACCOUNT_FILE, 'w', encoding='utf-8') as f:
        await f.write(json.dumps({"active_account": name}, ensure_ascii=False))


# ============== API 路由 ==============

@router.get("/api/accounts")
async def list_accounts() -> List[AccountInfo]:
    """获取所有账号列表"""
    ensure_state_dir()
    accounts = []
    active_account = await get_active_account_name()
    
    import time
    current_time = time.time()
    
    for filename in os.listdir(STATE_DIR):
        if filename.endswith(".json") and not filename.startswith("_"):
            name = filename[:-5]  # 去掉 .json 后缀
            try:
                data = await read_account_file(name)
                
                # 检测cookie状态
                cookie_status = data.get("cookie_status", "unknown")
                # 如果没有缓存状态，实时检测
                if cookie_status == "unknown":
                    cookies = data.get("cookies", [])
                    if not cookies:
                        cookie_status = "expired"
                    else:
                        # 检查关键cookie是否过期
                        has_expired = False
                        for cookie in cookies:
                            expires = cookie.get("expires", 0)
                            if expires > 0 and expires < current_time:
                                has_expired = True
                                break
                        cookie_status = "expired" if has_expired else "valid"
                
                accounts.append(AccountInfo(
                    name=name,
                    display_name=data.get("display_name", name),
                    created_at=data.get("created_at"),
                    last_used_at=data.get("last_used_at"),
                    is_active=(name == active_account),
                    risk_control_count=data.get("risk_control_count", 0),
                    cookie_status=cookie_status,
                    order=data.get("order")
                ))
            except Exception as e:
                print(f"读取账号文件 {filename} 失败: {e}")
    
    # 按创建时间排序

    has_order = any(account.order is not None for account in accounts)
    if has_order:
        accounts.sort(key=lambda x: (x.order is None, x.order if x.order is not None else 0, x.created_at or ""))
    else:
        accounts.sort(key=lambda x: x.created_at or "", reverse=True)
    return accounts


@router.post("/api/accounts/reorder")
async def reorder_accounts(payload: AccountOrderUpdate):
    """更新账号排序并写入 state 文件"""
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


@router.post("/api/accounts")
async def create_account(account: AccountCreate):
    """创建新账号"""
    ensure_state_dir()
    filepath = get_account_file_path(account.name)
    
    if os.path.exists(filepath):
        raise HTTPException(status_code=400, detail=f"账号 '{account.name}' 已存在")
    
    # 验证 state_content 是有效的 JSON
    try:
        state_data = json.loads(account.state_content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Cookie内容不是有效的JSON格式")
    
    # 构建完整的账号数据
    account_data = {
        "display_name": account.display_name,
        "created_at": datetime.now().isoformat(),
        "last_used_at": None,
        "risk_control_count": 0,
        "risk_control_history": [],
    }

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
    
    # 根据state_data的类型处理：如果是对象则合并，如果是数组则作为cookies
    if isinstance(state_data, dict):
        # 保存原始的state数据（cookies, env, headers等）
        for key in ["cookies", "env", "headers", "page", "storage"]:
            if key in state_data:
                account_data[key] = state_data[key]
    elif isinstance(state_data, list):
        # 如果是数组，假设是cookies数组
        account_data["cookies"] = state_data
    
    await write_account_file(account.name, account_data)
    
    # 如果是第一个账号，自动设为激活账号
    accounts = await list_accounts()
    if len(accounts) == 1:
        await set_active_account_name(account.name)
    
    return {"message": f"账号 '{account.display_name}' 创建成功"}


@router.get("/api/accounts/{name}")
async def get_account(name: str):
    """获取账号详情（包含Cookie用于复制）"""
    data = await read_account_file(name)
    active_account = await get_active_account_name()
    
    # 构建state_content用于复制功能
    state_content = None
    try:
        state_data = {
            "cookies": data.get("cookies", []),
            "env": data.get("env"),
            "headers": data.get("headers"),
            "page": data.get("page"),
            "storage": data.get("storage")
        }
        state_content = json.dumps(state_data, ensure_ascii=False, indent=2)
    except Exception:
        pass
    
    return {
        "name": name,
        "display_name": data.get("display_name", name),
        "created_at": data.get("created_at"),
        "last_used_at": data.get("last_used_at"),
        "is_active": (name == active_account),
        "risk_control_count": data.get("risk_control_count", 0),
        "risk_control_history": data.get("risk_control_history", []),
        "state_content": state_content
    }


@router.post("/api/accounts/{name}/test")
async def test_account_cookie(name: str):
    """测试账号Cookie是否有效"""
    try:
        data = await read_account_file(name)
        cookies = data.get("cookies", [])
        
        if not cookies:
            return {"valid": False, "message": f"账号 '{name}' 没有Cookie数据"}
        
        # 检查关键Cookie是否存在且未过期
        import time
        current_time = time.time()
        
        required_cookies = ["_m_h5_tk", "_m_h5_tk_enc", "cookie2"]
        found_cookies = set()
        expired_cookies = []
        
        for cookie in cookies:
            cookie_name = cookie.get("name", "")
            if cookie_name in required_cookies:
                found_cookies.add(cookie_name)
                # 检查过期时间
                expires = cookie.get("expires", 0)
                if expires > 0 and expires < current_time:
                    expired_cookies.append(cookie_name)
        
        if expired_cookies:
            return {
                "valid": False, 
                "message": f"账号 '{name}' 的以下Cookie已过期: {', '.join(expired_cookies)}"
            }
        
        missing = set(required_cookies) - found_cookies
        if missing:
            return {
                "valid": False,
                "message": f"账号 '{name}' 缺少关键Cookie: {', '.join(missing)}"
            }
        
        return {"valid": True, "message": f"账号 '{name}' 的Cookie看起来有效"}
        
    except HTTPException:
        raise
    except Exception as e:
        return {"valid": False, "message": f"测试账号 '{name}' 失败: {str(e)}"}


class DuplicateAccountRequest(BaseModel):
    """复制账号请求"""
    new_name: Optional[str] = None  # 可选，不传则自动生成


def generate_unique_account_name(base_name: str) -> str:
    """生成唯一账号名：原名称（副本1），原名称（副本2）..."""
    ensure_state_dir()
    
    # 去除可能已有的副本后缀，获取基础名称
    import re
    clean_name = re.sub(r'（副本\d+）$', '', base_name)
    
    # 查找所有以此名称开头的账号
    existing_names = set()
    for filename in os.listdir(STATE_DIR):
        if filename.endswith(".json") and not filename.startswith("_"):
            existing_names.add(filename[:-5])
    
    # 寻找可用的副本编号
    for i in range(1, 1000):
        new_name = f"{clean_name}（副本{i}）"
        if new_name not in existing_names:
            return new_name
    
    # 如果超过1000个副本，使用时间戳
    from datetime import datetime
    return f"{clean_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"


@router.post("/api/accounts/{name}/duplicate")
async def duplicate_account(name: str, request: DuplicateAccountRequest = None):
    """复制账号（创建副本），自动生成唯一名称"""
    try:
        # 读取源账号数据
        source_data = await read_account_file(name)
        
        # 确定新名称
        if request and request.new_name:
            new_name = request.new_name
            # 如果指定的名称已存在，自动重命名
            new_filepath = get_account_file_path(new_name)
            if os.path.exists(new_filepath):
                new_name = generate_unique_account_name(new_name)
        else:
            # 自动生成名称 - 基于display_name而不是文件名
            base_display_name = source_data.get("display_name", name)
            new_name = generate_unique_account_name(base_display_name)
        
        # 创建新账号数据
        new_data = source_data.copy()
        new_data["display_name"] = new_name
        new_data["created_at"] = datetime.now().isoformat()
        new_data["last_used_at"] = None
        new_data["risk_control_count"] = 0
        new_data["risk_control_history"] = []
        
        # 写入新账号文件
        await write_account_file(new_name, new_data)
        
        return {"message": f"账号 '{name}' 已成功复制为 '{new_name}'", "new_name": new_name}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"复制账号失败: {str(e)}")


@router.put("/api/accounts/{name}")
async def update_account(name: str, update: AccountUpdate):
    """更新账号信息"""
    data = await read_account_file(name)
    
    if update.display_name is not None:
        data["display_name"] = update.display_name
    
    if update.state_content is not None:
        try:
            state_data = json.loads(update.state_content)
            # 更新cookies和环境信息，保留其他元数据
            for key in ["cookies", "env", "headers", "page", "storage"]:
                if key in state_data:
                    data[key] = state_data[key]
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Cookie内容不是有效的JSON格式")
    
    await write_account_file(name, data)
    return {"message": f"账号 '{name}' 更新成功"}


@router.delete("/api/accounts/{name}")
async def delete_account(name: str):
    """删除账号"""
    filepath = get_account_file_path(name)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"账号 '{name}' 不存在")
    
    # 如果删除的是当前激活账号，需要清除激活状态
    active_account = await get_active_account_name()
    if name == active_account:
        if os.path.exists(ACTIVE_ACCOUNT_FILE):
            os.remove(ACTIVE_ACCOUNT_FILE)
    
    os.remove(filepath)
    return {"message": f"账号 '{name}' 已删除"}


@router.post("/api/accounts/{name}/activate")
async def activate_account(name: str):
    """激活账号（设为当前使用的账号）"""
    # 验证账号存在
    filepath = get_account_file_path(name)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"账号 '{name}' 不存在")
    
    await set_active_account_name(name)
    return {"message": f"账号 '{name}' 已激活"}


@router.post("/api/accounts/{name}/record-risk-control")
async def record_risk_control(name: str, reason: str = "未知原因", task_name: str = None):
    """记录风控触发"""
    data = await read_account_file(name)
    
    # 增加风控计数
    data["risk_control_count"] = data.get("risk_control_count", 0) + 1
    
    # 添加风控历史记录
    if "risk_control_history" not in data:
        data["risk_control_history"] = []
    
    data["risk_control_history"].append({
        "timestamp": datetime.now().isoformat(),
        "reason": reason,
        "task_name": task_name
    })
    
    # 只保留最近50条记录
    data["risk_control_history"] = data["risk_control_history"][-50:]
    
    await write_account_file(name, data)
    return {"message": "风控记录已保存"}


@router.post("/api/accounts/{name}/update-last-used")
async def update_last_used(name: str):
    """更新最后使用时间"""
    data = await read_account_file(name)
    data["last_used_at"] = datetime.now().isoformat()
    await write_account_file(name, data)
    return {"message": "使用时间已更新"}


async def get_account_state_for_scraper(name: str) -> dict:
    """
    获取账号的state数据供爬虫使用
    返回与原 xianyu_state.json 兼容的格式
    """
    data = await read_account_file(name)
    
    # 更新最后使用时间
    data["last_used_at"] = datetime.now().isoformat()
    await write_account_file(name, data)
    
    # 返回爬虫需要的数据
    return {
        "cookies": data.get("cookies", []),
        "env": data.get("env"),
        "headers": data.get("headers"),
        "page": data.get("page"),
        "storage": data.get("storage")
    }


async def get_next_available_account(current_account: str) -> Optional[str]:
    """
    获取下一个可用账号（用于风控切换）
    跳过当前账号，返回风控次数最少的账号
    """
    accounts = await list_accounts()
    
    # 过滤掉当前账号
    available = [a for a in accounts if a.name != current_account]
    
    if not available:
        return None
    
    # 按风控次数升序排序，返回风控最少的
    available.sort(key=lambda x: x.risk_control_count)
    return available[0].name
