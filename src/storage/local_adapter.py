"""
Local Storage Adapter - 本地文件存储适配器

实现 StorageInterface，使用本地 JSON/JSONL 文件存储数据。
保持向下兼容，与现有文件结构一致。
"""

import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from filelock import FileLock

from .interface import StorageInterface
from .utils import hash_password, verify_password, hash_token, generate_uuid
from src.config import get_env_value, get_bool_env_value

class LocalStorageAdapter(StorageInterface):
    """
    本地文件存储适配器
    
    使用 JSON 文件存储数据，保持与现有系统的兼容性。
    在 local 模式下，使用 .env 配置的单用户认证，不支持多用户功能。
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """
        初始化本地存储适配器
        
        Args:
            base_path: 基础路径，默认为项目根目录
        """
        if base_path:
            self.base_path = Path(base_path)
        else:
            # 默认为项目根目录
            self.base_path = Path(__file__).parent.parent.parent
        
        # 确保目录存在
        self.jsonl_dir = self.base_path / "jsonl"
        self.jsonl_dir.mkdir(exist_ok=True)
        
        self.state_dir = self.base_path / "state"
        self.state_dir.mkdir(exist_ok=True)
        
        self.prompts_dir = self.base_path / "prompts"
        self.bayes_dir = self.prompts_dir / "bayes"
    
    def _get_config_path(self) -> Path:
        """获取任务配置文件路径"""
        return self.base_path / "config.json"
    
    def _load_config(self) -> List[Dict[str, Any]]:
        """加载任务配置"""
        config_path = self._get_config_path()
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _save_config(self, config: List[Dict[str, Any]]):
        """保存任务配置"""
        config_path = self._get_config_path()
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    # ============== 用户管理（本地模式简化实现）==============
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """本地模式：返回 .env 配置的管理员用户"""
        if user_id == "admin" or user_id == "local_admin":
            return self._get_env_user()
        return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """本地模式：验证 .env 配置的用户名"""
        env_user = self._get_env_user()
        if env_user and env_user.get("username") == username:
            return env_user
        return None
    
    def _get_env_user(self) -> Optional[Dict[str, Any]]:
        """从环境变量获取用户配置"""
        username = os.getenv("WEB_USERNAME", "admin")
        password = os.getenv("WEB_PASSWORD", "admin123")
        if username:
            return {
                "id": "local_admin",
                "username": username,
                "password_hash": hash_password(password) if password else None,
                "role": "admin",
                "is_active": True,
                "email": None,
                "created_at": datetime.now().isoformat()
            }
        return None
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """本地模式不支持创建用户"""
        raise NotImplementedError("Local mode does not support multi-user. Use postgres backend.")
    
    def update_user(self, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """本地模式不支持更新用户"""
        raise NotImplementedError("Local mode does not support multi-user. Use postgres backend.")
    
    def list_users(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """本地模式返回单个管理员用户"""
        user = self._get_env_user()
        return [user] if user else []
    
    def delete_user(self, user_id: str) -> bool:
        """本地模式不支持删除用户"""
        raise NotImplementedError("Local mode does not support multi-user. Use postgres backend.")

    # ============== 用户组管理（本地模式兼容实现）==============

    def _build_local_default_group(self) -> Dict[str, Any]:
        """构造本地模式默认用户组快照"""
        return {
            "id": "local-super-admin-group",
            "code": "local_super_admin_group",
            "name": "本地超级管理员组",
            "description": "本地模式默认全量权限组",
            "is_system": True,
            "permissions": [
                {"category": "tasks", "enabled": True},
                {"category": "results", "enabled": True},
                {"category": "accounts", "enabled": True},
                {"category": "notify", "enabled": True},
                {"category": "ai", "enabled": True},
                {"category": "admin", "enabled": True},
            ],
        }

    def create_user_group(self, group_data: Dict[str, Any]) -> Dict[str, Any]:
        """本地模式不支持创建用户组"""
        raise NotImplementedError("Local mode does not support user groups. Use postgres backend.")

    def get_user_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        """本地模式仅返回默认组"""
        group = self._build_local_default_group()
        if group_id == group["id"]:
            return group
        return None

    def list_user_groups(self) -> List[Dict[str, Any]]:
        """本地模式返回默认组快照"""
        return [self._build_local_default_group()]

    def update_user_group(self, group_id: str, group_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """本地模式不支持更新用户组"""
        raise NotImplementedError("Local mode does not support user groups. Use postgres backend.")

    def delete_user_group(self, group_id: str) -> bool:
        """本地模式不支持删除用户组"""
        raise NotImplementedError("Local mode does not support user groups. Use postgres backend.")

    def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        """本地模式用户默认拥有全量权限组"""
        if user_id in ("local_admin", "admin", "anonymous"):
            return [self._build_local_default_group()]
        return []

    def set_user_groups(self, user_id: str, group_ids: List[str]) -> bool:
        """本地模式不支持设置用户组"""
        raise NotImplementedError("Local mode does not support user groups. Use postgres backend.")

    def get_group_permissions(self, group_id: str) -> List[Dict[str, Any]]:
        """本地模式返回默认组权限"""
        group = self.get_user_group(group_id)
        if not group:
            return []
        return group.get("permissions", [])

    def set_group_permissions(self, group_id: str, categories: Dict[str, bool]) -> bool:
        """本地模式不支持设置用户组权限"""
        raise NotImplementedError("Local mode does not support user groups. Use postgres backend.")
    
    # ============== 会话管理（本地模式简化实现）==============
    
    def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """本地模式：会话存储在内存中（由auth模块管理）"""
        return session_data
    
    def get_session_by_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """本地模式：会话验证由auth模块处理"""
        return None
    
    def delete_session(self, session_id: str) -> bool:
        """本地模式：会话由auth模块管理"""
        return True
    
    def delete_user_sessions(self, user_id: str) -> int:
        """本地模式：无需处理"""
        return 0
    
    # ============== 任务管理 ==============
    
    def get_tasks(self, owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取任务列表（本地模式忽略owner_id）"""
        return self._load_config()
    
    def get_task_by_name(self, task_name: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """根据任务名获取任务"""
        tasks = self._load_config()
        for task in tasks:
            if task.get("task_name") == task_name:
                return task
        return None
    
    def save_task(self, task: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存任务"""
        tasks = self._load_config()
        task_name = task.get("task_name")
        
        # 查找是否存在
        found = False
        for i, t in enumerate(tasks):
            if t.get("task_name") == task_name:
                tasks[i] = task
                found = True
                break
        
        if not found:
            # 设置order
            if "order" not in task:
                max_order = max([t.get("order", 0) for t in tasks], default=0)
                task["order"] = max_order + 1
            tasks.append(task)
        
        self._save_config(tasks)
        return task
    
    def delete_task(self, task_name: str, owner_id: Optional[str] = None) -> bool:
        """删除任务"""
        tasks = self._load_config()
        original_len = len(tasks)
        tasks = [t for t in tasks if t.get("task_name") != task_name]
        
        if len(tasks) < original_len:
            self._save_config(tasks)
            return True
        return False
    
    def update_task_order(self, ordered_names: List[str], owner_id: Optional[str] = None) -> bool:
        """更新任务排序"""
        tasks = self._load_config()
        name_to_task = {t["task_name"]: t for t in tasks}
        
        reordered = []
        for i, name in enumerate(ordered_names):
            if name in name_to_task:
                task = name_to_task[name]
                task["order"] = i + 1
                reordered.append(task)
        
        # 添加未在列表中的任务
        for task in tasks:
            if task["task_name"] not in ordered_names:
                reordered.append(task)
        
        self._save_config(reordered)
        return True
    
    # ============== 监控结果管理 ==============
    
    def _get_result_file(self, task_name: str) -> Path:
        """获取任务结果文件路径"""
        # 清理任务名作为文件名
        safe_name = task_name.replace(" ", "_").replace("/", "_")
        return self.jsonl_dir / f"{safe_name}_full_data.jsonl"
    
    def save_result(self, task_name: str, result: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存监控结果"""
        result_file = self._get_result_file(task_name)
        
        with open(result_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
        
        return result
    
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
        result_file = self._get_result_file(task_name)
        
        if not result_file.exists():
            return []
        
        results = []
        with open(result_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        result = json.loads(line)
                        
                        # 筛选推荐
                        if recommended_only and not result.get("is_recommended", False):
                            continue
                        
                        # 关键词筛选
                        if keyword:
                            title = result.get("商品信息", {}).get("商品标题", "")
                            if keyword.lower() not in title.lower():
                                continue
                        
                        results.append(result)
                    except json.JSONDecodeError:
                        continue
        
        # 分页
        return results[offset:offset + limit]
    
    def get_result_by_item_id(self, item_id: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """根据商品ID获取结果（需要遍历所有文件）"""
        for result_file in self.jsonl_dir.glob("*_full_data.jsonl"):
            with open(result_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            result = json.loads(line)
                            if result.get("商品信息", {}).get("商品ID") == item_id:
                                return result
                        except json.JSONDecodeError:
                            continue
        return None
    
    def delete_results(
        self, 
        task_name: str, 
        owner_id: Optional[str] = None,
        item_ids: Optional[List[str]] = None
    ) -> int:
        """删除监控结果"""
        result_file = self._get_result_file(task_name)
        
        if not result_file.exists():
            return 0
        
        if item_ids is None:
            # 删除所有
            result_file.unlink()
            return -1  # 表示删除了文件
        
        # 筛选保留的结果
        kept = []
        deleted = 0
        
        with open(result_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        result = json.loads(line)
                        result_item_id = result.get("商品信息", {}).get("商品ID")
                        if result_item_id in item_ids:
                            deleted += 1
                        else:
                            kept.append(line)
                    except json.JSONDecodeError:
                        kept.append(line)
        
        # 重写文件
        with open(result_file, 'w', encoding='utf-8') as f:
            f.writelines(kept)
        
        return deleted
    
    # ============== 贝叶斯配置管理 ==============
    
    def _get_bayes_file(self, version: str) -> Path:
        """获取贝叶斯配置文件路径"""
        return self.bayes_dir / f"{version}.json"
    
    def get_bayes_profile(self, version: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取贝叶斯配置"""
        bayes_file = self._get_bayes_file(version)
        if bayes_file.exists():
            with open(bayes_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def save_bayes_profile(self, profile: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存贝叶斯配置"""
        version = profile.get("version", "bayes_v1")
        bayes_file = self._get_bayes_file(version)
        
        with open(bayes_file, 'w', encoding='utf-8') as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        
        return profile
    
    def list_bayes_profiles(self, owner_id: Optional[str] = None, include_system: bool = True) -> List[Dict[str, Any]]:
        """获取贝叶斯配置列表"""
        profiles = []
        for bayes_file in self.bayes_dir.glob("*.json"):
            try:
                with open(bayes_file, 'r', encoding='utf-8') as f:
                    profile = json.load(f)
                    profiles.append({
                        "version": profile.get("version", bayes_file.stem),
                        "file": str(bayes_file)
                    })
            except (json.JSONDecodeError, IOError):
                continue
        return profiles
    
    # ============== 贝叶斯样本管理 ==============
    
    def get_bayes_samples(
        self, 
        profile_version: str, 
        owner_id: Optional[str] = None,
        label: Optional[int] = None,
        include_system: bool = True
    ) -> List[Dict[str, Any]]:
        """获取贝叶斯样本"""
        profile = self.get_bayes_profile(profile_version)
        if not profile:
            return []
        
        samples = []
        samples_data = profile.get("_samples", {})
        
        for category, sample_list in samples_data.items():
            if category.startswith("_"):
                continue
            
            category_label = 1 if category == "可信" else 0
            
            if label is not None and category_label != label:
                continue
            
            for sample in sample_list:
                normalized_sample = dict(sample or {})
                normalized_sample["label"] = category_label
                normalized_sample["profile_version"] = profile_version
                normalized_sample["id"] = (
                    normalized_sample.get("id")
                    or normalized_sample.get("sample_id")
                    or normalized_sample.get("item_id")
                    or generate_uuid()
                )
                samples.append(normalized_sample)
        
        return samples
    
    def add_bayes_sample(self, sample: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """添加贝叶斯样本"""
        profile_version = sample.get("profile_version", "bayes_v1")
        profile = self.get_bayes_profile(profile_version) or {"version": profile_version, "_samples": {"可信": [], "不可信": []}}
        
        if "_samples" not in profile:
            profile["_samples"] = {"可信": [], "不可信": []}
        
        label = sample.get("label", 1)
        category = "可信" if label == 1 else "不可信"
        
        if category not in profile["_samples"]:
            profile["_samples"][category] = []
        
        # 添加样本
        new_sample = {
            "id": sample.get("id") or generate_uuid(),
            "name": sample.get("name", "用户反馈样本"),
            "vector": sample.get("vector", []),
            "label": label,
            "source": sample.get("source", "user"),
            "item_id": sample.get("item_id"),
            "note": sample.get("note"),
            "timestamp": datetime.now().isoformat()
        }
        
        profile["_samples"][category].append(new_sample)
        self.save_bayes_profile(profile)
        
        return new_sample
    
    def delete_bayes_sample(self, sample_id: str, owner_id: Optional[str] = None) -> bool:
        """删除贝叶斯样本（本地模式按 id 或 item_id 删除）"""
        sample_id_str = str(sample_id or "")
        for bayes_file in self.bayes_dir.glob("*.json"):
            try:
                with open(bayes_file, 'r', encoding='utf-8') as f:
                    profile = json.load(f)
                
                modified = False
                for category in ["可信", "不可信"]:
                    if category in profile.get("_samples", {}):
                        original_len = len(profile["_samples"][category])
                        profile["_samples"][category] = [
                            s for s in profile["_samples"][category] 
                            if str(
                                s.get("id")
                                or s.get("sample_id")
                                or s.get("item_id")
                                or ""
                            ) != sample_id_str
                        ]
                        if len(profile["_samples"][category]) < original_len:
                            modified = True
                
                if modified:
                    with open(bayes_file, 'w', encoding='utf-8') as f:
                        json.dump(profile, f, ensure_ascii=False, indent=2)
                    return True
            except (json.JSONDecodeError, IOError):
                continue
        
        return False
    
    # ============== 用户反馈管理 ==============
    
    def save_feedback(
        self, 
        user_id: str,
        result_id: str, 
        feedback_type: str, 
        feature_vector: List[float]
    ) -> Dict[str, Any]:
        """保存用户反馈记录（本地模式通过样本层承载闭环数据）"""
        return {
            "id": generate_uuid(),
            "user_id": user_id or "local_admin",
            "result_id": result_id,
            "feedback_type": feedback_type,
            "feature_vector": feature_vector,
            "created_at": datetime.now().isoformat()
        }
    
    def get_feedbacks(
        self, 
        user_id: Optional[str] = None,
        result_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取用户反馈（从样本中筛选）"""
        samples = self.get_bayes_samples("bayes_v1")
        feedbacks = []
        for sample in samples:
            source = str(sample.get("source") or "").strip().lower()
            if source not in {"user", "user_feedback"}:
                continue
            feedbacks.append({
                "id": sample.get("id"),
                "user_id": user_id or "local_admin",
                "result_id": sample.get("item_id"),
                "feedback_type": "trusted" if sample.get("label") == 1 else "untrusted",
                "feature_vector": sample.get("vector") or [],
                "created_at": sample.get("timestamp"),
            })
        
        if result_id:
            feedbacks = [f for f in feedbacks if f.get("result_id") == result_id]
        
        return feedbacks[:limit]
    
    def delete_feedback(
        self,
        user_id: str,
        result_id: str
    ) -> bool:
        """删除指定结果的反馈（本地模式：清理关联贝叶斯样本）"""
        result_id_str = str(result_id or "")
        for bayes_file in self.bayes_dir.glob("*.json"):
            try:
                with open(bayes_file, 'r', encoding='utf-8') as f:
                    profile = json.load(f)
                
                modified = False
                for category in ["可信", "不可信"]:
                    samples = profile.get("_samples", {}).get(category, [])
                    original_len = len(samples)
                    profile["_samples"][category] = [
                        s for s in samples
                        if not (
                            str(s.get("item_id") or "") == result_id_str
                            and str(s.get("source") or "").lower() in {"user", "user_feedback"}
                        )
                    ]
                    if len(profile["_samples"][category]) < original_len:
                        modified = True
                
                if modified:
                    with open(bayes_file, 'w', encoding='utf-8') as f:
                        json.dump(profile, f, ensure_ascii=False, indent=2)
                    return True
            except (json.JSONDecodeError, IOError):
                continue
        return False
    
    # ============== AI标准管理 ==============
    
    def _get_criteria_dir(self) -> Path:
        """获取AI标准目录"""
        return self.base_path / "requirement"
    
    def get_ai_criteria(self, criteria_id: str) -> Optional[Dict[str, Any]]:
        """获取AI标准"""
        criteria_dir = self._get_criteria_dir()
        criteria_file = criteria_dir / f"{criteria_id}.txt"
        
        if criteria_file.exists():
            with open(criteria_file, 'r', encoding='utf-8') as f:
                content = f.read()
            return {
                "id": criteria_id,
                "name": criteria_id,
                "content": content
            }
        return None
    
    def list_ai_criteria(self, owner_id: Optional[str] = None, include_system: bool = True) -> List[Dict[str, Any]]:
        """获取AI标准列表"""
        criteria_dir = self._get_criteria_dir()
        criteria_list = []
        
        if criteria_dir.exists():
            for criteria_file in criteria_dir.glob("*.txt"):
                criteria_list.append({
                    "id": criteria_file.stem,
                    "name": criteria_file.stem,
                    "file": str(criteria_file)
                })
        
        return criteria_list
    
    def save_ai_criteria(self, criteria: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
        """保存AI标准"""
        criteria_dir = self._get_criteria_dir()
        criteria_dir.mkdir(exist_ok=True)
        
        name = criteria.get("name", criteria.get("id", "custom_criteria"))
        content = criteria.get("content", "")
        
        criteria_file = criteria_dir / f"{name}.txt"
        with open(criteria_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {"id": name, "name": name, "content": content}
    
    def delete_ai_criteria(self, criteria_id: str, owner_id: Optional[str] = None) -> bool:
        """删除AI标准"""
        criteria_dir = self._get_criteria_dir()
        criteria_file = criteria_dir / f"{criteria_id}.txt"
        
        if criteria_file.exists():
            criteria_file.unlink()
            return True
        return False
    
    # ============== 用户API配置管理（本地模式使用.env）==============
    
    def get_user_api_configs(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户API配置（本地模式从 .env 读取有效配置）"""
        api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
        api_base_url = str(os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or "").strip()
        model_name = str(os.getenv("OPENAI_MODEL_NAME") or os.getenv("OPENAI_MODEL") or "").strip()

        # 本地模式下仅在至少一个关键字段存在时计入资产，避免“未配置却显示1条”
        if not any([api_key, api_base_url, model_name]):
            return []

        return [{
            "id": "env_config",
            "provider": "openai",
            "name": "环境变量配置",
            "api_base_url": api_base_url,
            "model": model_name,
            "is_default": True
        }]
    
    def save_user_api_config(self, user_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """本地模式不支持保存API配置"""
        raise NotImplementedError("Local mode uses .env for API config. Use postgres backend for multi-user.")
    
    def delete_user_api_config(self, config_id: str, user_id: str) -> bool:
        """本地模式不支持删除API配置"""
        return False
    
    def get_default_api_config(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取默认API配置"""
        configs = self.get_user_api_configs(user_id)
        return configs[0] if configs else None
    
    # ============== 用户通知配置管理（本地模式使用.env）==============
    
    def get_user_notification_configs(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户通知配置（本地模式从 .env 提取已启用且数据完整的通知资产）。"""
        configs: List[Dict[str, Any]] = []

        def _enabled(key: str) -> bool:
            return bool(get_bool_env_value(key, False))

        def _has_value(key: str) -> bool:
            return bool(str(get_env_value(key, "") or "").strip())

        channel_rules = [
            {
                "id": "wx_app",
                "channel_type": "wx_app",
                "name": "企业微信应用",
                "enabled_key": "WX_APP_ENABLED",
                "required_keys": ["WX_CORP_ID", "WX_AGENT_ID", "WX_SECRET"],
            },
            {
                "id": "wx_bot",
                "channel_type": "wx_bot",
                "name": "企业微信机器人",
                "enabled_key": "WX_BOT_ENABLED",
                "required_keys": ["WX_BOT_URL"],
            },
            {
                "id": "dingtalk",
                "channel_type": "dingtalk",
                "name": "钉钉机器人",
                "enabled_key": "DINGTALK_ENABLED",
                "required_keys": ["DINGTALK_WEBHOOK"],
            },
            {
                "id": "telegram",
                "channel_type": "telegram",
                "name": "Telegram",
                "enabled_key": "TELEGRAM_ENABLED",
                "required_keys": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
            },
            {
                "id": "ntfy",
                "channel_type": "ntfy",
                "name": "NTFY",
                "enabled_key": "NTFY_ENABLED",
                "required_keys": ["NTFY_TOPIC_URL"],
            },
            {
                "id": "gotify",
                "channel_type": "gotify",
                "name": "Gotify",
                "enabled_key": "GOTIFY_ENABLED",
                "required_keys": ["GOTIFY_URL", "GOTIFY_TOKEN"],
            },
            {
                "id": "bark",
                "channel_type": "bark",
                "name": "Bark",
                "enabled_key": "BARK_ENABLED",
                "required_keys": ["BARK_URL"],
            },
            {
                "id": "webhook",
                "channel_type": "webhook",
                "name": "Webhook",
                "enabled_key": "WEBHOOK_ENABLED",
                "required_keys": ["WEBHOOK_URL"],
            },
        ]

        for rule in channel_rules:
            enabled = _enabled(rule["enabled_key"])
            if not all(_has_value(key) for key in rule["required_keys"]):
                continue
            configs.append(
                {
                    "id": rule["id"],
                    "channel_type": rule["channel_type"],
                    "name": rule["name"],
                    "is_enabled": enabled,
                }
            )

        return configs

    def save_user_notification_config(self, user_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """本地模式不支持保存通知配置"""
        raise NotImplementedError("Local mode uses .env for notification config. Use postgres backend for multi-user.")
    
    def delete_user_notification_config(self, config_id: str, user_id: str) -> bool:
        """本地模式不支持删除通知配置"""
        return False
    
    # ============== 用户平台账号管理 ==============
    
    def get_user_platform_accounts(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户平台账号（从state目录读取）"""
        accounts = []
        for account_file in self.state_dir.glob("*.json"):
            try:
                with open(account_file, 'r', encoding='utf-8') as f:
                    account = json.load(f)
                    account["id"] = account_file.stem
                    account["file"] = str(account_file)
                    accounts.append(account)
            except (json.JSONDecodeError, IOError):
                continue
        return accounts
    
    def save_user_platform_account(self, user_id: str, account: Dict[str, Any]) -> Dict[str, Any]:
        """保存用户平台账号"""
        account_id = account.get("id") or f"auto_account_{len(list(self.state_dir.glob('*.json'))) + 1}"
        account_file = self.state_dir / f"{account_id}.json"
        
        with open(account_file, 'w', encoding='utf-8') as f:
            json.dump(account, f, ensure_ascii=False, indent=2)
        
        account["id"] = account_id
        return account
    
    def delete_user_platform_account(self, account_id: str, user_id: str) -> bool:
        """删除用户平台账号"""
        account_file = self.state_dir / f"{account_id}.json"
        if account_file.exists():
            account_file.unlink()
            return True
        return False
    
    def update_platform_account_cookies(self, account_id: str, user_id: str, cookies: str) -> bool:
        """更新平台账号Cookie"""
        account_file = self.state_dir / f"{account_id}.json"
        if not account_file.exists():
            return False
        
        with open(account_file, 'r', encoding='utf-8') as f:
            account = json.load(f)
        
        account["cookies"] = json.loads(cookies) if isinstance(cookies, str) else cookies
        account["last_used_at"] = datetime.now().isoformat()
        
        with open(account_file, 'w', encoding='utf-8') as f:
            json.dump(account, f, ensure_ascii=False, indent=2)
        
        return True
    
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
        """记录审计日志（本地模式记录到日志文件）"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,
            "ip_address": ip_address
        }
        
        # 可以选择写入日志文件或使用logging
        # 这里简单返回
        return log_entry
    
    def get_audit_logs(
        self, 
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取审计日志（本地模式返回空列表）"""
        return []

