"""结果视图屏蔽、黑名单和偏好 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query, Request

from src.storage import get_storage
from src.storage.result_management import ResultManagementError, ResultManagementRepository
from src.web.auth import get_current_user, require_category
from src.web.result_filters import InvalidRule, ResultViewHttpError, rule_matches, validate_rule


router = APIRouter()


def _error(code: str, message: str, status: int) -> ResultViewHttpError:
    return ResultViewHttpError(status, code, message)


def _repo(request: Request) -> ResultManagementRepository:
    user = get_current_user(request)
    owner = user.get("user_id") if user else None
    if not owner:
        raise _error("UNAUTHORIZED", "请先登录。", 401)
    try:
        return ResultManagementRepository(get_storage(), str(owner))
    except ResultManagementError as exc:
        raise _error(exc.code, str(exc), exc.status) from None


def _call(operation):
    try:
        return operation()
    except ResultManagementError as exc:
        raise _error(exc.code, str(exc), exc.status) from None


def _task_ref(repo: ResultManagementRepository, value: str | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    try:
        value = str(UUID(value))
    except (TypeError, ValueError, AttributeError):
        raise _error("INVALID_TASK", "任务标识无效。", 400) from None
    for task in repo.storage.get_tasks(owner_id=repo.owner):
        ref = task.get("stable_task_id") if repo.local else task.get("id")
        if ref and str(ref) == value:
            return value, str(task.get("task_name") or "")[:255]
    raise _error("NOT_FOUND", "任务不存在。", 404)


def _rule_data(repo: ResultManagementRepository, data: dict, existing: dict | None = None) -> dict:
    if not isinstance(data, dict):
        raise _error("INVALID_INPUT", "规则格式无效。", 400)
    scope = data.get("scope", existing.get("scope") if existing else "task")
    if scope not in ("task", "global"):
        raise _error("INVALID_SCOPE", "规则作用范围无效。", 400)
    task_ref = data.get("task_ref", existing.get("task_ref") if existing else None)
    if scope == "task" and not task_ref:
        raise _error("INVALID_TASK", "请选择规则所属任务。", 400)
    if scope == "global" and task_ref:
        raise _error("INVALID_SCOPE", "个人全局规则不能同时指定任务。", 400)
    task_ref, task_name = _task_ref(repo, task_ref)
    kind = data.get("kind", existing.get("kind") if existing else "keyword")
    pattern = data.get("pattern", existing.get("pattern") if existing else None)
    try:
        validate_rule(kind, pattern)
    except InvalidRule as exc:
        raise _error("UNSUPPORTED_RULE", str(exc), 400) from None
    enabled = data.get("enabled", existing.get("enabled") if existing else True)
    if type(enabled) is not bool:
        raise _error("INVALID_INPUT", "规则启用状态无效。", 400)
    return {"scope": scope, "task_ref": task_ref, "task_name_snapshot": task_name,
            "kind": kind, "pattern": pattern, "enabled": enabled}


def _revision(data: dict, *, allow_zero: bool = False) -> int:
    value = data.get("expected_revision") if isinstance(data, dict) else None
    if type(value) is not int or value < (0 if allow_zero else 1):
        raise _error("INVALID_REVISION", "请提供有效的 expected_revision。", 400)
    return value


@router.get("/api/result-management/hidden-items")
@require_category("results")
async def hidden_items(request: Request, limit: int = Query(100, ge=1, le=100), cursor: str = ""):
    rows = _call(lambda: _repo(request).hidden_items())
    if cursor and (not cursor.isdigit() or len(cursor) > 128):
        raise _error("INVALID_CURSOR", "游标无效。", 400)
    after = [row for row in rows if row["item_id"] > cursor]
    page = after[:limit]
    return {"items": page, "next_cursor": page[-1]["item_id"] if len(after) > limit else None}


@router.put("/api/result-management/hidden-items/{item_id}")
@require_category("results")
async def hide_item(request: Request, item_id: str):
    if not item_id.isdigit() or len(item_id) > 128:
        raise _error("INVALID_ID", "商品 ID 无效。", 400)
    _call(lambda: _repo(request).set_hidden(item_id, True))
    return {"item_id": item_id, "hidden": True}


@router.delete("/api/result-management/hidden-items/{item_id}")
@require_category("results")
async def restore_item(request: Request, item_id: str):
    if not item_id.isdigit() or len(item_id) > 128:
        raise _error("INVALID_ID", "商品 ID 无效。", 400)
    _call(lambda: _repo(request).set_hidden(item_id, False))
    return {"item_id": item_id, "hidden": False}


@router.get("/api/result-management/blacklist-rules")
@require_category("results")
async def blacklist_rules(request: Request, limit: int = Query(50, ge=1, le=50), cursor: str = ""):
    rows = _call(lambda: _repo(request).rules())
    if cursor:
        try:
            cursor = str(UUID(cursor))
        except (ValueError, TypeError, AttributeError):
            raise _error("INVALID_CURSOR", "游标无效。", 400) from None
    after = [row for row in rows if row["id"] > cursor]
    page = after[:limit]
    return {"items": page, "next_cursor": page[-1]["id"] if len(after) > limit else None}


@router.post("/api/result-management/blacklist-rules", status_code=201)
@require_category("results")
async def create_blacklist_rule(request: Request, payload: dict = Body(...)):
    if _revision(payload, allow_zero=True) != 0:
        raise _error("INVALID_REVISION", "新规则的 expected_revision 必须为 0。", 400)
    repo = _repo(request)
    data = _rule_data(repo, payload)
    return _call(lambda: repo.create_rule(data))


@router.patch("/api/result-management/blacklist-rules/{rule_id}")
@require_category("results")
async def update_blacklist_rule(request: Request, rule_id: str, payload: dict = Body(...)):
    revision = _revision(payload)
    repo = _repo(request)
    existing = next((row for row in _call(repo.rules) if row["id"] == rule_id), None)
    if existing is None:
        raise _error("NOT_FOUND", "规则不存在。", 404)
    data = _rule_data(repo, payload, existing)
    return _call(lambda: repo.change_rule(rule_id, revision, data))


@router.delete("/api/result-management/blacklist-rules/{rule_id}")
@require_category("results")
async def delete_blacklist_rule(request: Request, rule_id: str, expected_revision: int = Query(..., ge=1)):
    _call(lambda: _repo(request).change_rule(rule_id, expected_revision, None))
    return {"deleted": True}


@router.post("/api/result-management/blacklist-rules/preview")
@require_category("results")
async def preview_blacklist_rule(request: Request, payload: dict = Body(...)):
    repo = _repo(request)
    data = _rule_data(repo, payload)
    filename = payload.get("filename", "all")
    if not isinstance(filename, str):
        raise _error("INVALID_INPUT", "结果文件名无效。", 400)
    from src.web.result_manager import _load_results_for_view, _extract_item_id
    records, tasks = await _load_results_for_view(filename, None if repo.local else repo.owner,
                                                  repo.storage, preview=True)
    by_name = {str(task.get("task_name")): str(task.get("stable_task_id") if repo.local else task.get("id"))
               for task in tasks}
    matched = [record for record in records if rule_matches(
        record, {**data, "enabled": True}, by_name.get(str(record.get("任务名称"))))]
    return {"sampled": len(records), "matched": len(matched),
            "items": [{"item_id": _extract_item_id(record),
                       "title": str((record.get("商品信息") or {}).get("商品标题") or "")[:160]}
                      for record in matched[:20]]}


@router.get("/api/result-management/view-preferences")
@require_category("results")
async def view_preferences(request: Request):
    return _call(lambda: _repo(request).preference())


@router.put("/api/result-management/view-preferences")
@require_category("results")
async def save_view_preferences(request: Request, payload: dict = Body(...)):
    revision = _revision(payload, allow_zero=True)
    repo = _repo(request)
    task_ref, _ = _task_ref(repo, payload.get("task_ref"))
    filters = payload.get("filters", {})
    if not isinstance(filters, dict) or set(filters) - {
        "recommended_only", "task_name", "keyword", "ai_criteria", "manual_keyword", "include_hidden"
    }:
        raise _error("INVALID_FILTER", "筛选偏好含不支持的字段。", 400)
    if (type(filters.get("recommended_only", False)) is not bool
        or type(filters.get("include_hidden", False)) is not bool
        or any(not isinstance(filters.get(key, ""), str) or len(filters.get(key, "")) > 128
               for key in ("task_name", "keyword", "ai_criteria", "manual_keyword"))):
        raise _error("INVALID_FILTER", "筛选偏好值无效。", 400)
    sort_by, sort_order = payload.get("sort_by", "crawl_time"), payload.get("sort_order", "desc")
    if sort_by not in ("crawl_time", "publish_time", "price") or sort_order not in ("asc", "desc"):
        raise _error("INVALID_SORT", "排序偏好无效。", 400)
    return _call(lambda: repo.save_preference({"task_ref": task_ref, "filters": filters,
                                               "sort_by": sort_by, "sort_order": sort_order}, revision))
