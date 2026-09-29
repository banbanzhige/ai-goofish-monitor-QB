"""价格观察只读 API；结果页筛选和权限沿用既有结果视图。"""

from __future__ import annotations

import base64
import binascii
import csv
import io
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.storage import get_storage
from src.storage.price_observations import (
    PriceObservationError, PriceObservationRepository, summarize_item, summarize_market,
)
from src.web.auth import get_current_user, require_category
from src.web.result_filters import ResultViewHttpError
from src.web.result_manager import _extract_item_id, _query_result_view, _safe_task_filename


router = APIRouter()


def _window(since: str | None, until: str | None) -> tuple[datetime, datetime]:
    def parse(value: str) -> datetime:
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            raise ResultViewHttpError(400, "INVALID_WINDOW", "时间窗格式无效，请使用带时区的 ISO 时间。") from None
        if result.tzinfo is None:
            raise ResultViewHttpError(400, "INVALID_WINDOW", "时间窗必须包含时区。")
        return result.astimezone(timezone.utc)

    end = parse(until) if until else datetime.now(timezone.utc)
    start = parse(since) if since else end - timedelta(days=30)
    if not start < end or end - start > timedelta(days=365) or end > datetime.now(timezone.utc):
        raise ResultViewHttpError(400, "INVALID_WINDOW", "时间窗须大于零且不超过 365 天。")
    return start, end


def _task_refs(tasks: list[dict], owner_id: str | None) -> dict[str, str]:
    key = "id" if owner_id else "stable_task_id"
    return {str(task.get("task_name")): str(task[key])
            for task in tasks if task.get(key)}


def _selected_task_ref(tasks: list[dict], owner_id: str | None,
                       filename: str, task_ref: str | None,
                       visible: list[dict]) -> str | None:
    known = {str(task.get("id") if owner_id else task.get("stable_task_id")): task
             for task in tasks if task.get("id" if owner_id else "stable_task_id")}
    if task_ref is not None:
        try:
            task_ref = str(UUID(task_ref))
        except (TypeError, ValueError, AttributeError):
            raise ResultViewHttpError(400, "INVALID_TASK", "任务标识无效。") from None
        if task_ref not in known:
            raise ResultViewHttpError(404, "NOT_FOUND", "任务不存在。")
    if filename != "all":
        matched = next((ref for ref, task in known.items()
                        if _safe_task_filename(task.get("task_name")) == filename), None)
        if matched is None:
            candidate_refs = {str(record.get("_result_task_ref")) for record in visible
                              if record.get("_result_task_ref") in known}
            if len(candidate_refs) == 1:
                matched = next(iter(candidate_refs))
        if matched is None or (task_ref is not None and task_ref != matched):
            raise ResultViewHttpError(404, "NOT_FOUND", "任务不存在。")
        return matched
    return task_ref


def _cursor_encode(row: dict) -> str:
    data = json.dumps([row["observed_at"], row["id"]], separators=(",", ":"))
    return base64.urlsafe_b64encode(data.encode("utf-8")).decode("ascii").rstrip("=")


def _cursor_decode(value: str | None) -> tuple[str, str] | None:
    if value is None:
        return None
    try:
        if len(value) > 256:
            raise ValueError
        values = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        if (not isinstance(values, list) or len(values) != 2
            or any(not isinstance(part, str) for part in values)):
            raise ValueError
        return values[0], values[1]
    except (ValueError, UnicodeError, TypeError, binascii.Error):
        raise ResultViewHttpError(400, "INVALID_CURSOR", "分页游标无效。") from None


async def _scope(request: Request, *, filename: str, task_ref: str | None,
                 since: str | None, until: str | None, recommended_only: bool,
                 task_name: str | None, keyword: str | None, ai_criteria: str | None,
                 manual_keyword: str | None, include_hidden: bool,
                 item_id: str | None = None):
    start, end = _window(since, until)
    visible, _, tasks, owner_id, _ = await _query_result_view(
        filename, request, recommended_only=recommended_only, task_name=task_name,
        keyword=keyword, ai_criteria=ai_criteria, sort_by="crawl_time", sort_order="desc",
        manual_keyword=manual_keyword, include_hidden=include_hidden)
    selected = _selected_task_ref(tasks, owner_id, filename, task_ref, visible)
    refs = _task_refs(tasks, owner_id)
    visible_pairs = set()
    for record in visible:
        current_item = _extract_item_id(record)
        current_ref = record.get("_result_task_ref") or (
            None if record.get("stable_task_id") else refs.get(str(record.get("任务名称"))))
        if current_item and current_ref and (selected is None or selected == current_ref):
            visible_pairs.add((current_ref, current_item))
    if item_id is not None and not any(pair[1] == item_id for pair in visible_pairs):
        raise ResultViewHttpError(404, "NOT_FOUND", "商品观察不存在。")
    user = get_current_user(request)
    owner = str(user.get("user_id")) if user else ""
    if not owner:
        raise ResultViewHttpError(401, "UNAUTHORIZED", "请先登录。")
    try:
        repo = PriceObservationRepository(get_storage(), owner)
    except PriceObservationError:
        raise ResultViewHttpError(503, "PRICE_UNAVAILABLE", "价格观察暂时无法读取。") from None
    return repo, visible_pairs, selected, start, end


async def _query(request: Request, *, filename: str, task_ref: str | None,
                 since: str | None, until: str | None, recommended_only: bool,
                 task_name: str | None, keyword: str | None, ai_criteria: str | None,
                 manual_keyword: str | None, include_hidden: bool,
                 item_id: str | None = None) -> tuple[list[dict], datetime, datetime]:
    repo, visible_pairs, selected, start, end = await _scope(
        request, filename=filename, task_ref=task_ref, since=since, until=until,
        recommended_only=recommended_only, task_name=task_name, keyword=keyword,
        ai_criteria=ai_criteria, manual_keyword=manual_keyword,
        include_hidden=include_hidden, item_id=item_id)
    if not visible_pairs:
        return [], start, end
    try:
        rows = repo.list_observations(since=start, until=end, task_ref=selected,
                                      item_id=item_id, limit=50001)
    except PriceObservationError:
        raise ResultViewHttpError(503, "PRICE_UNAVAILABLE", "价格观察暂时无法读取。") from None
    if len(rows) > 50000:
        raise ResultViewHttpError(429, "PRICE_LIMIT", "价格观察超过 50,000 条，请缩小时间或任务范围。")
    return [row for row in rows if (row["task_ref"], row["item_id"]) in visible_pairs], start, end


@router.get("/api/price-observations/items/{item_id}")
@require_category("results")
async def item_prices(request: Request, item_id: str, filename: str = "all",
                      task_ref: str | None = None, since: str | None = None,
                      until: str | None = None, limit: int = 20,
                      cursor: str | None = None, recommended_only: bool = False,
                      task_name: str | None = None, keyword: str | None = None,
                      ai_criteria: str | None = None, manual_keyword: str | None = None,
                      include_hidden: bool = False):
    if not 1 <= len(item_id) <= 128 or not 1 <= limit <= 100:
        raise ResultViewHttpError(400, "INVALID_INPUT", "商品标识或分页长度无效。")
    rows, start, end = await _query(
        request, filename=filename, task_ref=task_ref, since=since, until=until,
        recommended_only=recommended_only, task_name=task_name, keyword=keyword,
        ai_criteria=ai_criteria, manual_keyword=manual_keyword,
        include_hidden=include_hidden, item_id=item_id)
    by_task: dict[str, list[dict]] = {}
    for row in rows:
        by_task.setdefault(row["task_ref"], []).append(row)
    if len(by_task) > 100:
        raise ResultViewHttpError(429, "TASK_LIMIT", "商品关联任务过多，请先选择具体任务。")
    anchor = _cursor_decode(cursor)
    if anchor:
        try:
            datetime.fromisoformat(anchor[0].replace("Z", "+00:00"))
            UUID(anchor[1])
        except (ValueError, TypeError):
            raise ResultViewHttpError(400, "INVALID_CURSOR", "分页游标无效。") from None
    if anchor:
        rows = [row for row in rows if (row["observed_at"], row["id"]) < anchor]
    page = rows[:limit]
    public_fields = ("task_ref", "task_name_snapshot", "item_id", "observed_at",
                     "currency", "raw_price", "amount", "source")
    public_page = [{field: row.get(field) for field in public_fields} for row in page]
    return {"items": public_page,
            "next_cursor": _cursor_encode(page[-1]) if len(rows) > limit else None,
            "summaries": [{"task_ref": ref, **summarize_item(task_rows)}
                          for ref, task_rows in sorted(by_task.items())],
            "since": start.isoformat(), "until": end.isoformat()}


@router.get("/api/price-observations/summary")
@require_category("results")
async def price_summary(request: Request, filename: str = "all", task_ref: str | None = None,
                        since: str | None = None, until: str | None = None,
                        limit: int = 20, cursor: str | None = None,
                        recommended_only: bool = False, task_name: str | None = None,
                        keyword: str | None = None, ai_criteria: str | None = None,
                        manual_keyword: str | None = None, include_hidden: bool = False):
    if not 1 <= limit <= 100:
        raise ResultViewHttpError(400, "INVALID_PAGE", "分页长度无效。")
    anchor = _cursor_decode(cursor)
    if anchor:
        try:
            UUID(anchor[0])
        except (ValueError, TypeError):
            raise ResultViewHttpError(400, "INVALID_CURSOR", "分页游标无效。") from None
    rows, start, end = await _query(
        request, filename=filename, task_ref=task_ref, since=since, until=until,
        recommended_only=recommended_only, task_name=task_name, keyword=keyword,
        ai_criteria=ai_criteria, manual_keyword=manual_keyword, include_hidden=include_hidden)
    groups = summarize_market(rows)
    if anchor:
        groups = [group for group in groups if (group["task_ref"], group["currency"]) > anchor]
    page = groups[:limit]
    next_cursor = (_cursor_encode({"observed_at": page[-1]["task_ref"], "id": page[-1]["currency"]})
                   if len(groups) > limit else None)
    return {"groups": page, "next_cursor": next_cursor,
            "observation_count": len(rows), "since": start.isoformat(), "until": end.isoformat()}


@router.get("/api/price-observations/export.csv")
@require_category("results")
async def export_prices(request: Request, filename: str = "all", task_ref: str | None = None,
                        since: str | None = None, until: str | None = None,
                        recommended_only: bool = False, task_name: str | None = None,
                        keyword: str | None = None, ai_criteria: str | None = None,
                        manual_keyword: str | None = None, include_hidden: bool = False):
    repo, visible_pairs, selected, start, end = await _scope(
        request, filename=filename, task_ref=task_ref, since=since, until=until,
        recommended_only=recommended_only, task_name=task_name, keyword=keyword,
        ai_criteria=ai_criteria, manual_keyword=manual_keyword, include_hidden=include_hidden)

    if not visible_pairs:
        async def empty_csv():
            yield "任务标识,任务名称快照,商品ID,观察时间UTC,币种,价格原文,标准化金额,来源\r\n"
        return StreamingResponse(empty_csv(), media_type="text/csv; charset=utf-8",
                                 headers={"Content-Disposition": "attachment; filename=price-observations.csv"})

    # 响应头发送前先验算上限与状态；超过时返回明确错误，绝不产生截断 CSV。
    reader = repo.iter_observations(since=start, until=end, task_ref=selected)
    candidate_count = 0
    try:
        for row in reader:
            if (row["task_ref"], row["item_id"]) not in visible_pairs:
                continue
            candidate_count += 1
            if candidate_count > 50000:
                raise ResultViewHttpError(429, "PRICE_LIMIT", "价格观察超过 50,000 条，请缩小时间或任务范围。")
    except PriceObservationError:
        raise ResultViewHttpError(503, "PRICE_UNAVAILABLE", "价格观察暂时无法读取。") from None
    finally:
        reader.close()

    def cell(value) -> str:
        value = "" if value is None else str(value)
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value

    async def stream():
        columns = ("任务标识", "任务名称快照", "商品ID", "观察时间UTC", "币种", "价格原文", "标准化金额", "来源")
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(columns)
        yield output.getvalue()
        reader = repo.iter_observations(since=start, until=end, task_ref=selected)
        emitted = 0
        try:
            for row in reader:
                if await request.is_disconnected():
                    return
                if (row["task_ref"], row["item_id"]) not in visible_pairs:
                    continue
                emitted += 1
                if emitted > 50000:
                    raise PriceObservationError("价格观察在导出时超过上限。")
                output.seek(0)
                output.truncate(0)
                writer.writerow([cell(row.get(field)) for field in (
                    "task_ref", "task_name_snapshot", "item_id", "observed_at",
                    "currency", "raw_price", "amount", "source")])
                yield output.getvalue()
        finally:
            reader.close()

    return StreamingResponse(stream(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=price-observations.csv"})
