import os
import re
import json
import aiofiles
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Request

from src.web.models import DeleteResultItemRequest, DeleteResultsBatchRequest
from src.storage import get_storage
from src.web.auth import get_current_user, is_multi_user_mode
from src.logging_config import get_logger


router = APIRouter()
logger = get_logger(__name__, service="web")

TASK_NAME_KEY = "任务名称"
KEYWORD_KEY = "搜索关键字"
CRITERIA_KEY = "AI标准"
PRODUCT_KEY = "商品信息"
LINK_KEY = "商品链接"
TITLE_KEY = "商品标题"
DESC_KEY = "商品描述"
SELLER_NAME_KEY = "卖家昵称"
PRICE_KEY = "当前售价"
PUBLISH_TIME_KEY = "发布时间"
CRAWL_TIME_KEY = "公开信息浏览时间"

RECOMMENDED_LEVELS = {"STRONG_BUY", "CAUTIOUS_BUY", "CONDITIONAL_BUY"}
USER_FEEDBACK_SOURCES = {"user", "user_feedback"}
FEEDBACK_STATUS_BY_LABEL = {1: "trusted", 0: "untrusted"}


def _get_owner_id(request: Optional[Request] = None) -> Optional[str]:
    if not is_multi_user_mode() or request is None:
        return None
    user = get_current_user(request)
    if not user:
        return None
    user_id = user.get("user_id") or user.get("id")
    return str(user_id) if user_id else None


def _safe_task_filename(task_name: str) -> str:
    safe = str(task_name or "").replace(" ", "_").replace("/", "_")
    return f"{safe}_full_data.jsonl"


def _is_ai_recommended(ai_analysis: dict) -> bool:
    if not isinstance(ai_analysis, dict):
        return False
    level = ai_analysis.get("recommendation_level")
    if isinstance(level, str):
        return level in RECOMMENDED_LEVELS
    return ai_analysis.get("is_recommended") is True


def _extract_item_id(item: Dict[str, Any]) -> str:
    info = item.get(PRODUCT_KEY, {}) if isinstance(item, dict) else {}
    link = str(info.get(LINK_KEY, ""))
    match = re.search(r"id=(\d+)", link)
    return match.group(1) if match else ""


def _decorate_record(record: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(record or {})
    normalized.setdefault(TASK_NAME_KEY, task.get("task_name"))
    normalized.setdefault(KEYWORD_KEY, task.get("keyword"))
    normalized.setdefault(CRITERIA_KEY, task.get("ai_prompt_criteria_file", "N/A"))
    if "ai_analysis" not in normalized and "AI分析" in normalized:
        normalized["ai_analysis"] = normalized.get("AI分析")
    if "AI分析" not in normalized and "ai_analysis" in normalized:
        normalized["AI分析"] = normalized.get("ai_analysis")
    return normalized


def _matches_filters(record: Dict[str, Any], filters) -> bool:
    if not filters:
        return True

    ai_analysis = record.get("ai_analysis") or record.get("AI分析") or {}
    if filters.recommended_only and not _is_ai_recommended(ai_analysis):
        return False

    if filters.task_name and filters.task_name != "all":
        if record.get(TASK_NAME_KEY) != filters.task_name:
            return False

    if filters.keyword and filters.keyword != "all":
        if record.get(KEYWORD_KEY) != filters.keyword:
            return False

    if filters.ai_criteria and filters.ai_criteria != "all":
        if record.get(CRITERIA_KEY) != filters.ai_criteria:
            return False

    if filters.manual_keyword:
        manual_keyword_lower = filters.manual_keyword.lower()
        item_info = record.get(PRODUCT_KEY, {})
        product_title = str(item_info.get(TITLE_KEY, "")).lower()
        product_desc = str(item_info.get(DESC_KEY, "")).lower()
        seller_name = str(item_info.get(SELLER_NAME_KEY, "")).lower()
        current_price = str(item_info.get(PRICE_KEY, "")).lower()
        ai_reason = str(ai_analysis.get("reason", "")).lower()

        if (
            manual_keyword_lower not in product_title
            and manual_keyword_lower not in product_desc
            and manual_keyword_lower not in seller_name
            and manual_keyword_lower not in current_price
            and manual_keyword_lower not in ai_reason
        ):
            return False

    return True


async def _load_records(filepath: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
        async for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


async def _write_records(filepath: str, records: List[Dict[str, Any]]) -> None:
    async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
        for record in records:
            await f.write(json.dumps(record, ensure_ascii=False) + "\n")


async def _delete_records_in_file(filepath: str, filters, item_ids: List[str]) -> int:
    records = await _load_records(filepath)
    initial_count = len(records)
    if item_ids:
        records = [record for record in records if _extract_item_id(record) not in item_ids]
    else:
        records = [record for record in records if not _matches_filters(record, filters)]
    deleted_count = initial_count - len(records)
    if deleted_count:
        await _write_records(filepath, records)
    return deleted_count


def _resolve_task_by_filename(filename: str, tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")
    for task in tasks:
        if _safe_task_filename(task.get("task_name")) == filename:
            return task
    return None


def _sort_results(records: List[Dict[str, Any]], sort_by: str, sort_order: str) -> List[Dict[str, Any]]:
    def get_sort_key(item: Dict[str, Any]):
        info = item.get(PRODUCT_KEY, {})
        if sort_by == "publish_time":
            return info.get(PUBLISH_TIME_KEY, "0000-00-00 00:00")
        if sort_by == "price":
            price_str = str(info.get(PRICE_KEY, "0")).replace("￥", "").replace(",", "").strip()
            try:
                return float(price_str)
            except (ValueError, TypeError):
                return 0.0
        return item.get(CRAWL_TIME_KEY, "")

    records.sort(key=get_sort_key, reverse=(sort_order == "desc"))
    return records



def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    """解析ISO时间字符串，兼容 Z 结尾。"""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _build_feedback_status_map(owner_id: Optional[str]) -> Dict[str, str]:
    """构建 item_id -> feedback_status 映射，用于结果卡片回显反馈状态。"""
    storage = get_storage()
    status_map: Dict[str, str] = {}
    timestamp_map: Dict[str, Optional[datetime]] = {}

    # 兼容历史 profile_version=v1 与当前 bayes_v1
    for profile_version in ("bayes_v1", "v1"):
        try:
            samples = storage.get_bayes_samples(
                profile_version=profile_version,
                owner_id=owner_id,
                include_system=True
            )
        except Exception as e:
            logger.warning(
                "读取反馈样本失败，反馈状态将降级为空",
                extra={"event": "result_feedback_status_load_failed", "owner_id": owner_id, "profile_version": profile_version},
                exc_info=e
            )
            continue

        for sample in samples or []:
            source = str(sample.get("source") or "").strip().lower()
            if source not in USER_FEEDBACK_SOURCES:
                continue

            item_id = str(sample.get("item_id") or "").strip()
            if not item_id:
                continue

            label = sample.get("label")
            status = FEEDBACK_STATUS_BY_LABEL.get(label)
            if not status:
                continue

            current_time = _parse_iso_datetime(sample.get("created_at") or sample.get("timestamp"))
            previous_time = timestamp_map.get(item_id)
            should_update = item_id not in status_map
            if not should_update and current_time and previous_time:
                should_update = current_time >= previous_time
            elif not should_update and current_time and previous_time is None:
                should_update = True

            if should_update:
                status_map[item_id] = status
                timestamp_map[item_id] = current_time

    return status_map


def _attach_feedback_status(records: List[Dict[str, Any]], status_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """将反馈状态附加到结果记录。"""
    if not records:
        return records

    for record in records:
        if not isinstance(record, dict):
            continue
        item_id = _extract_item_id(record)
        record["feedback_status"] = status_map.get(item_id, "") if item_id else ""

    return records


@router.get("/api/results/files")
async def list_result_files(request: Request):
    """列出结果文件列表"""
    owner_id = _get_owner_id(request)
    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        files = [_safe_task_filename(task.get("task_name")) for task in tasks]
        return {"files": files}

    jsonl_dir = "jsonl"
    if not os.path.isdir(jsonl_dir):
        return {"files": []}
    files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]
    return {"files": files}


@router.delete("/api/results/files/{filename}")
async def delete_result_file(filename: str, request: Request):
    """删除结果文件"""
    owner_id = _get_owner_id(request)
    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        target_tasks = tasks if filename == "all" else []
        if filename != "all":
            matched_task = _resolve_task_by_filename(filename, tasks)
            if not matched_task:
                raise HTTPException(status_code=404, detail="结果文件未找到。")
            target_tasks = [matched_task]

        deleted_count = 0
        for task in target_tasks:
            deleted = storage.delete_results(task.get("task_name"), owner_id=owner_id)
            if deleted != 0:
                deleted_count += 1
        return {"message": f"已删除 {deleted_count} 个任务结果。"}

    if filename == "all":
        jsonl_dir = "jsonl"
        if not os.path.isdir(jsonl_dir):
            return {"message": "结果文件目录未找到。"}

        files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]
        if not files:
            return {"message": "没有结果文件需要删除。"}

        deleted_count = 0
        for file in files:
            try:
                os.remove(os.path.join(jsonl_dir, file))
                deleted_count += 1
            except Exception as e:
                logger.warning(f"删除文件失败: {file}, 错误: {e}", extra={"event": "result_file_delete_failed"})
        return {"message": f"已成功删除 {deleted_count} 个结果文件。"}

    if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")

    filepath = os.path.join("jsonl", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="结果文件未找到。")

    try:
        os.remove(filepath)
        return {"message": f"结果文件 '{filename}' 已成功删除。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除结果文件时出错: {e}")


@router.post("/api/results/delete")
async def delete_result_item(payload: DeleteResultItemRequest, request: Request):
    """删除单条结果记录"""
    owner_id = _get_owner_id(request)
    item_id_to_delete = _extract_item_id(payload.item)
    if not item_id_to_delete:
        raise HTTPException(status_code=400, detail="未识别到要删除的商品ID。")

    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        target_tasks = tasks if payload.filename == "all" else []
        if payload.filename != "all":
            matched_task = _resolve_task_by_filename(payload.filename, tasks)
            if not matched_task:
                raise HTTPException(status_code=404, detail="结果文件未找到。")
            target_tasks = [matched_task]

        for task in target_tasks:
            deleted_count = storage.delete_results(task.get("task_name"), owner_id=owner_id, item_ids=[item_id_to_delete])
            if deleted_count > 0:
                return {"message": "商品记录已成功删除。", "file": _safe_task_filename(task.get("task_name"))}
        raise HTTPException(status_code=404, detail="商品记录未找到。")

    filename = payload.filename
    if filename == "all":
        jsonl_dir = "jsonl"
        if not os.path.isdir(jsonl_dir):
            raise HTTPException(status_code=404, detail="结果文件目录未找到。")

        files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]
        if not files:
            raise HTTPException(status_code=404, detail="没有结果文件需要删除。")

        for file in files:
            filepath = os.path.join(jsonl_dir, file)
            records = await _load_records(filepath)
            filtered = [record for record in records if _extract_item_id(record) != item_id_to_delete]
            if len(filtered) < len(records):
                await _write_records(filepath, filtered)
                return {"message": "商品记录已成功删除。", "file": file}
        raise HTTPException(status_code=404, detail="商品记录未找到。")

    if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")

    filepath = os.path.join("jsonl", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="结果文件未找到。")

    records = await _load_records(filepath)
    filtered = [record for record in records if _extract_item_id(record) != item_id_to_delete]
    if len(filtered) == len(records):
        raise HTTPException(status_code=404, detail="商品记录未找到。")

    await _write_records(filepath, filtered)
    return {"message": "商品记录已成功删除。"}


@router.post("/api/results/delete-batch")
async def delete_results_batch(payload: DeleteResultsBatchRequest, request: Request):
    """按筛选条件或勾选项批量删除结果记录"""
    owner_id = _get_owner_id(request)
    filename = payload.filename
    filters = payload.filters
    item_ids = [item_id for item_id in (payload.item_ids or []) if item_id]

    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        target_tasks = tasks if filename == "all" else []
        if filename != "all":
            matched_task = _resolve_task_by_filename(filename, tasks)
            if not matched_task:
                raise HTTPException(status_code=404, detail="结果文件未找到。")
            target_tasks = [matched_task]

        total_deleted = 0
        touched_files: List[str] = []

        for task in target_tasks:
            task_name = task.get("task_name")
            if item_ids:
                deleted_count = storage.delete_results(task_name, owner_id=owner_id, item_ids=item_ids)
            else:
                records = storage.get_results(task_name, owner_id=owner_id, limit=50000, offset=0)
                records = [_decorate_record(record, task) for record in records]
                matched_ids = [
                    _extract_item_id(record)
                    for record in records
                    if _extract_item_id(record) and _matches_filters(record, filters)
                ]
                deleted_count = storage.delete_results(task_name, owner_id=owner_id, item_ids=matched_ids) if matched_ids else 0

            if deleted_count > 0:
                total_deleted += deleted_count
                touched_files.append(_safe_task_filename(task_name))

        return {
            "message": f"已删除 {total_deleted} 条记录。",
            "deleted_count": total_deleted,
            "files": touched_files,
        }

    if filename != "all":
        if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
            raise HTTPException(status_code=400, detail="无效的文件名。")

        filepath = os.path.join("jsonl", filename)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="结果文件未找到。")

        deleted_count = await _delete_records_in_file(filepath, filters, item_ids)
        return {
            "message": f"已删除 {deleted_count} 条记录。",
            "deleted_count": deleted_count,
            "files": [filename],
        }

    jsonl_dir = "jsonl"
    if not os.path.isdir(jsonl_dir):
        raise HTTPException(status_code=404, detail="结果文件目录未找到。")

    files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]
    if not files:
        raise HTTPException(status_code=404, detail="没有结果文件需要删除。")

    total_deleted = 0
    touched_files = []
    for file in files:
        filepath = os.path.join(jsonl_dir, file)
        deleted_count = await _delete_records_in_file(filepath, filters, item_ids)
        if deleted_count:
            total_deleted += deleted_count
            touched_files.append(file)

    return {
        "message": f"已删除 {total_deleted} 条记录。",
        "deleted_count": total_deleted,
        "files": touched_files,
    }


@router.get("/api/results/{filename}")
async def get_result_file_content(
    filename: str,
    request: Request,
    page: int = 1,
    limit: int = 20,
    recommended_only: bool = False,
    task_name: str = None,
    keyword: str = None,
    ai_criteria: str = None,
    sort_by: str = "crawl_time",
    sort_order: str = "desc",
    manual_keyword: str = None,
):
    """读取结果内容，支持分页、筛选和排序"""
    owner_id = _get_owner_id(request)
    results: List[Dict[str, Any]] = []
    tasks: List[Dict[str, Any]] = []

    if owner_id:
        storage = get_storage()
        tasks = storage.get_tasks(owner_id=owner_id)
        target_tasks = tasks if filename == "all" else []
        if filename != "all":
            matched_task = _resolve_task_by_filename(filename, tasks)
            if not matched_task:
                raise HTTPException(status_code=404, detail="结果文件未找到。")
            target_tasks = [matched_task]

        for task in target_tasks:
            task_records = storage.get_results(task.get("task_name"), owner_id=owner_id, limit=50000, offset=0)
            results.extend([_decorate_record(record, task) for record in task_records])
    else:
        if filename == "all":
            jsonl_dir = "jsonl"
            if not os.path.isdir(jsonl_dir):
                raise HTTPException(status_code=404, detail="结果文件目录未找到。")

            files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]
            for file in files:
                filepath = os.path.join(jsonl_dir, file)
                try:
                    results.extend(await _load_records(filepath))
                except Exception as e:
                    logger.warning(f"读取文件失败: {file}, 错误: {e}", extra={"event": "result_file_load_failed"})
        else:
            if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
                raise HTTPException(status_code=400, detail="无效的文件名。")
            filepath = os.path.join("jsonl", filename)
            if not os.path.exists(filepath):
                raise HTTPException(status_code=404, detail="结果文件未找到。")
            try:
                results = await _load_records(filepath)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"读取结果文件时出错: {e}")

        try:
            async with aiofiles.open("config.json", "r", encoding="utf-8") as f:
                tasks = json.loads(await f.read())
        except Exception:
            tasks = []

    class _Filters:
        def __init__(self):
            self.recommended_only = recommended_only
            self.task_name = task_name
            self.keyword = keyword
            self.ai_criteria = ai_criteria
            self.manual_keyword = manual_keyword

    filtered_results = [record for record in results if _matches_filters(record, _Filters())]
    _sort_results(filtered_results, sort_by, sort_order)

    total_items = len(filtered_results)
    start = max(0, (page - 1) * limit)
    end = start + max(1, limit)
    paginated_results = filtered_results[start:end]
    feedback_status_map = _build_feedback_status_map(owner_id=owner_id)
    _attach_feedback_status(paginated_results, feedback_status_map)

    return {
        "total_items": total_items,
        "page": page,
        "limit": limit,
        "items": paginated_results,
        "tasks": tasks,
    }


