"""用户文件作用域工具。

统一管理 prompts/criteria/requirement/bayes 的“虚拟路径 -> 实际路径”映射：
- 单用户模式：继续使用仓库根目录下的原有共享目录
- 多用户模式：优先读取 state/user_files/{owner_id}/...，不存在时回退共享目录
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional


_USER_FILE_ROOT = Path("state") / "user_files"
_KIND_CONFIG: Dict[str, Dict[str, object]] = {
    "prompts": {
        "shared_dir": Path("prompts"),
        "user_subdir": "prompts",
        "ext": ".txt",
    },
    "criteria": {
        "shared_dir": Path("criteria"),
        "user_subdir": "criteria",
        "ext": ".txt",
    },
    "requirement": {
        "shared_dir": Path("requirement"),
        "user_subdir": "requirement",
        "ext": ".txt",
    },
    "bayes": {
        "shared_dir": Path("prompts") / "bayes",
        "user_subdir": "bayes",
        "ext": ".json",
    },
}


def normalize_owner_id(owner_id: Optional[str]) -> Optional[str]:
    """标准化 owner_id。"""
    text = str(owner_id or "").strip()
    return text or None


def _sanitize_owner_fragment(owner_id: str) -> str:
    """将 owner_id 转为可用于目录名的片段。"""
    return re.sub(r"[^0-9a-zA-Z_-]", "_", owner_id)


def _validate_kind(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized not in _KIND_CONFIG:
        raise ValueError(f"不支持的文件类型: {kind}")
    return normalized


def _safe_filename(filename: str) -> str:
    text = str(filename or "").strip().replace("\\", "/")
    text = text.split("/")[-1]
    if not text:
        raise ValueError("文件名不能为空")
    return text


def get_user_scoped_path(kind: str, filename: str, owner_id: Optional[str]) -> Path:
    """返回用户私有路径（不做存在性判断）。"""
    normalized_owner = normalize_owner_id(owner_id)
    if not normalized_owner:
        raise ValueError("缺少 owner_id，无法构建用户私有路径")
    normalized_kind = _validate_kind(kind)
    config = _KIND_CONFIG[normalized_kind]
    safe_owner = _sanitize_owner_fragment(normalized_owner)
    safe_name = _safe_filename(filename)
    return _USER_FILE_ROOT / safe_owner / str(config["user_subdir"]) / safe_name


def get_shared_path(kind: str, filename: str) -> Path:
    """返回共享目录路径。"""
    normalized_kind = _validate_kind(kind)
    config = _KIND_CONFIG[normalized_kind]
    safe_name = _safe_filename(filename)
    return Path(str(config["shared_dir"])) / safe_name


def get_scoped_read_candidates(kind: str, filename: str, owner_id: Optional[str]) -> List[Path]:
    """返回读取候选路径（按优先级）。"""
    candidates: List[Path] = []
    normalized_owner = normalize_owner_id(owner_id)
    if normalized_owner:
        candidates.append(get_user_scoped_path(kind, filename, normalized_owner))
    candidates.append(get_shared_path(kind, filename))
    return candidates


def resolve_scoped_path(kind: str, filename: str, owner_id: Optional[str], for_write: bool = False) -> Path:
    """解析作用域路径。

    for_write=True 时：
    - 有 owner_id：返回用户私有路径（并创建父目录）
    - 无 owner_id：返回共享路径（并创建父目录）
    """
    normalized_owner = normalize_owner_id(owner_id)
    if for_write:
        if normalized_owner:
            target = get_user_scoped_path(kind, filename, normalized_owner)
        else:
            target = get_shared_path(kind, filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    for path in get_scoped_read_candidates(kind, filename, normalized_owner):
        if path.exists():
            return path
    if normalized_owner:
        return get_user_scoped_path(kind, filename, normalized_owner)
    return get_shared_path(kind, filename)


def list_scoped_files(kind: str, owner_id: Optional[str], include_shared: bool = True) -> List[str]:
    """列出作用域内文件名。"""
    normalized_kind = _validate_kind(kind)
    config = _KIND_CONFIG[normalized_kind]
    expected_ext = str(config.get("ext") or "").lower()

    names = set()
    normalized_owner = normalize_owner_id(owner_id)

    if normalized_owner:
        user_dir = get_user_scoped_path(normalized_kind, "__placeholder__", normalized_owner).parent
        if user_dir.exists():
            for entry in user_dir.iterdir():
                if not entry.is_file():
                    continue
                if expected_ext and entry.suffix.lower() != expected_ext:
                    continue
                names.add(entry.name)

    if include_shared:
        shared_dir = Path(str(config["shared_dir"]))
        if shared_dir.exists():
            for entry in shared_dir.iterdir():
                if not entry.is_file():
                    continue
                if expected_ext and entry.suffix.lower() != expected_ext:
                    continue
                names.add(entry.name)

    return sorted(names)


def build_virtual_prompt_path(reference_file: Optional[str]) -> str:
    """将参考模板字段标准化为 prompts/{filename}.txt 形式。"""
    text = str(reference_file or "").strip().replace("\\", "/")
    if not text:
        return "prompts/base_prompt.txt"
    if text.startswith("prompts/"):
        return text
    if "/" not in text:
        return f"prompts/{text}"
    return text


def resolve_virtual_task_file(raw_path: str, owner_id: Optional[str], for_write: bool = False) -> Path:
    """把任务中的虚拟路径解析为实际文件路径。"""
    text = str(raw_path or "").strip()
    if not text:
        return Path(text)
    normalized = text.replace("\\", "/")

    # 绝对路径按原样处理（兼容历史任务）
    if os.path.isabs(normalized) or Path(normalized).drive:
        return Path(normalized)

    if normalized.startswith("prompts/bayes/"):
        filename = normalized.split("/", 2)[-1]
        return resolve_scoped_path("bayes", filename, owner_id=owner_id, for_write=for_write)
    if normalized.startswith("prompts/"):
        filename = normalized.split("/", 1)[-1]
        return resolve_scoped_path("prompts", filename, owner_id=owner_id, for_write=for_write)
    if normalized.startswith("criteria/"):
        filename = normalized.split("/", 1)[-1]
        return resolve_scoped_path("criteria", filename, owner_id=owner_id, for_write=for_write)
    if normalized.startswith("requirement/"):
        filename = normalized.split("/", 1)[-1]
        return resolve_scoped_path("requirement", filename, owner_id=owner_id, for_write=for_write)

    # 兼容老数据：裸文件名默认按 prompts 处理
    if "/" not in normalized and normalized.lower().endswith(".txt"):
        return resolve_scoped_path("prompts", normalized, owner_id=owner_id, for_write=for_write)

    return Path(normalized)
