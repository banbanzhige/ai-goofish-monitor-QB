"""结果视图的持久化状态；所有写入均限定当前认证 owner。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from src.storage.local_adapter import LocalStorageAdapter
from src.storage.upstream_local import LocalUpstreamStateError


logger = logging.getLogger(__name__)
MAX_HIDDEN = 10000
MAX_RULES = 50


class ResultManagementError(RuntimeError):
    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code = code
        self.status = status


def _uuid(value: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ResultManagementError("INVALID_ID", "标识无效。", 400) from None


def _plain(row: dict) -> dict:
    return {key: value.isoformat() if isinstance(value, datetime) else str(value)
            if isinstance(value, UUID) else value for key, value in row.items()}


class ResultManagementRepository:
    def __init__(self, storage: Any, owner_id: str):
        self.storage = storage
        self.local = isinstance(storage, LocalStorageAdapter)
        self.owner = "local_admin" if self.local else _uuid(owner_id)
        if self.local and owner_id != "local_admin":
            raise ResultManagementError("FORBIDDEN", "无权访问结果管理状态。", 403)

    def _store(self):
        try:
            return self.storage.upstream_store(owner_id=self.owner)
        except (LocalUpstreamStateError, PermissionError):
            raise ResultManagementError("SCHEMA_UNAVAILABLE", "本地数据尚未升级到 v2 或状态无法校验。", 503) from None

    def _local_read(self, name: str) -> list[dict]:
        try:
            return self._store().read(name)["records"]
        except LocalUpstreamStateError:
            raise ResultManagementError("STATE_UNAVAILABLE", "结果管理状态无法读取。", 503) from None

    def _local_mutate(self, name: str, transform) -> None:
        store = self._store()
        def wrapped(records):
            try:
                return transform(records)
            except ResultManagementError as exc:
                raise LocalUpstreamStateError(f"result-management:{exc.code}") from None
        for _ in range(3):
            try:
                revision = store.read(name)["revision"]
                store.update(name, expected_revision=revision, transform=wrapped)
                return
            except LocalUpstreamStateError as exc:
                marker = str(exc)
                if marker.startswith("result-management:"):
                    code = marker.split(":", 1)[1]
                    messages = {
                        "LIMIT_EXCEEDED": ("记录已达上限。", 429),
                        "REVISION_CONFLICT": ("状态已改变，请刷新后重试。", 409),
                        "NOT_FOUND": ("规则不存在。", 404),
                    }
                    message, status = messages[code]
                    raise ResultManagementError(code, message, status) from None
                if "revision conflict" in str(exc):
                    continue
                raise ResultManagementError("STATE_UNAVAILABLE", "结果管理状态无法更新。", 503) from None
        raise ResultManagementError("REVISION_CONFLICT", "状态已被其他请求修改，请刷新后重试。", 409)

    def _pg_rows(self, query: str, params: dict) -> list[dict]:
        try:
            with self.storage.get_session() as session:
                self._pg_version(session)
                return [_plain(dict(row)) for row in session.execute(text(query), params).mappings().all()]
        except ResultManagementError:
            raise
        except Exception:
            logger.exception("Result management read failed")
            raise ResultManagementError("STATE_UNAVAILABLE", "结果管理状态无法读取。", 503) from None

    @staticmethod
    def _pg_version(session) -> None:
        if session.execute(text("SELECT version FROM public.app_schema_version LIMIT 2")).fetchall() != [(2,)]:
            raise ResultManagementError("SCHEMA_UNAVAILABLE", "数据库尚未升级到 v2。", 503)

    def hidden_items(self) -> list[dict]:
        if self.local:
            return sorted(self._local_read("hidden_items"), key=lambda row: row["item_id"])
        rows = self._pg_rows(
            "SELECT item_id, created_at FROM public.result_hidden_items "
            "WHERE owner_id=:owner ORDER BY item_id LIMIT :limit",
            {"owner": self.owner, "limit": MAX_HIDDEN + 1})
        if len(rows) > MAX_HIDDEN:
            raise ResultManagementError("LIMIT_EXCEEDED", "屏蔽记录超过读取上限。", 429)
        return rows

    def view_state(self) -> tuple[set[str], list[dict]]:
        """一次请求内同时读取屏蔽和规则，避免两个读取跨版本。"""
        if self.local:
            try:
                snapshot = self._store().read_many(("hidden_items", "blacklist_rules"))
            except LocalUpstreamStateError:
                raise ResultManagementError("STATE_UNAVAILABLE", "结果管理状态无法读取。", 503) from None
            hidden = snapshot["hidden_items"]["records"]
            rules = snapshot["blacklist_rules"]["records"]
        else:
            try:
                with self.storage.get_session() as session:
                    session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
                    self._pg_version(session)
                    hidden = [dict(row) for row in session.execute(text(
                        "SELECT item_id FROM public.result_hidden_items WHERE owner_id=:owner "
                        "ORDER BY item_id LIMIT :limit"),
                        {"owner": self.owner, "limit": MAX_HIDDEN + 1}).mappings().all()]
                    rules = [_plain(dict(row)) for row in session.execute(text(
                        "SELECT id,scope,task_ref,task_name_snapshot,kind,pattern,enabled,revision "
                        "FROM public.result_blacklist_rules WHERE owner_id=:owner ORDER BY id LIMIT :limit"),
                        {"owner": self.owner, "limit": MAX_RULES + 1}).mappings().all()]
            except ResultManagementError:
                raise
            except Exception:
                logger.exception("Result management snapshot failed")
                raise ResultManagementError("STATE_UNAVAILABLE", "结果管理状态无法读取。", 503) from None
        if len(hidden) > MAX_HIDDEN or len(rules) > MAX_RULES:
            raise ResultManagementError("LIMIT_EXCEEDED", "结果管理记录超过读取上限。", 429)
        return {row["item_id"] for row in hidden}, rules

    def set_hidden(self, item_id: str, hidden: bool) -> None:
        if self.local:
            def transform(records):
                exists = any(row.get("item_id") == item_id for row in records)
                if hidden and not exists:
                    if len(records) >= MAX_HIDDEN:
                        raise ResultManagementError("LIMIT_EXCEEDED", "屏蔽记录已达上限。", 429)
                    records.append({"owner_id": self.owner, "item_id": item_id,
                                    "created_at": datetime.now().astimezone().isoformat()})
                elif not hidden and exists:
                    records = [row for row in records if row.get("item_id") != item_id]
                return records
            self._local_mutate("hidden_items", transform)
            return
        statement = (
            "INSERT INTO public.result_hidden_items (owner_id,item_id) VALUES (:owner,:item) "
            "ON CONFLICT DO NOTHING" if hidden else
            "DELETE FROM public.result_hidden_items WHERE owner_id=:owner AND item_id=:item")
        try:
            with self.storage.get_session() as session:
                self._pg_version(session)
                if hidden:
                    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:owner, 0))"),
                                    {"owner": self.owner})
                    exists = session.execute(text(
                        "SELECT 1 FROM public.result_hidden_items WHERE owner_id=:owner AND item_id=:item"),
                        {"owner": self.owner, "item": item_id}).first()
                    if not exists:
                        count = session.execute(text(
                            "SELECT count(*) FROM public.result_hidden_items WHERE owner_id=:owner"),
                            {"owner": self.owner}).scalar_one()
                        if count >= MAX_HIDDEN:
                            raise ResultManagementError("LIMIT_EXCEEDED", "屏蔽记录已达上限。", 429)
                session.execute(text(statement), {"owner": self.owner, "item": item_id})
        except ResultManagementError:
            raise
        except Exception:
            logger.exception("Result hidden item update failed")
            raise ResultManagementError("STATE_UNAVAILABLE", "屏蔽状态无法更新。", 503) from None

    def rules(self) -> list[dict]:
        if self.local:
            rows = self._local_read("blacklist_rules")
        else:
            rows = self._pg_rows(
                "SELECT id,scope,task_ref,task_name_snapshot,kind,pattern,enabled,revision,created_at,updated_at "
                "FROM public.result_blacklist_rules WHERE owner_id=:owner ORDER BY id LIMIT :limit",
                {"owner": self.owner, "limit": MAX_RULES + 1})
        if len(rows) > MAX_RULES:
            raise ResultManagementError("LIMIT_EXCEEDED", "黑名单规则超过读取上限。", 429)
        return sorted(rows, key=lambda row: row["id"])

    def create_rule(self, data: dict) -> dict:
        if self.local and len(self.rules()) >= MAX_RULES:
            raise ResultManagementError("LIMIT_EXCEEDED", "黑名单规则已达上限。", 429)
        now = datetime.now().astimezone().isoformat()
        row = {"id": str(uuid4()), "scope": data["scope"], "task_ref": data.get("task_ref"),
               "task_name_snapshot": data.get("task_name_snapshot"), "kind": data["kind"],
               "pattern": data["pattern"], "enabled": data["enabled"], "revision": 1,
               "created_at": now, "updated_at": now}
        if self.local:
            def transform(records):
                if len(records) >= MAX_RULES:
                    raise ResultManagementError("LIMIT_EXCEEDED", "黑名单规则已达上限。", 429)
                return records + [{"owner_id": self.owner, **row}]
            self._local_mutate("blacklist_rules", transform)
        else:
            try:
                with self.storage.get_session() as session:
                    self._pg_version(session)
                    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:owner, 1))"),
                                    {"owner": self.owner})
                    count = session.execute(text(
                        "SELECT count(*) FROM public.result_blacklist_rules WHERE owner_id=:owner"),
                        {"owner": self.owner}).scalar_one()
                    if count >= MAX_RULES:
                        raise ResultManagementError("LIMIT_EXCEEDED", "黑名单规则已达上限。", 429)
                    session.execute(text(
                        "INSERT INTO public.result_blacklist_rules "
                        "(id,owner_id,scope,task_ref,task_name_snapshot,kind,pattern,enabled,revision) "
                        "VALUES (:id,:owner,:scope,:task_ref,:task_name_snapshot,:kind,:pattern,:enabled,1)"
                    ), {"owner": self.owner, **{key: row[key] for key in (
                        "id", "scope", "task_ref", "task_name_snapshot", "kind", "pattern", "enabled")}})
            except ResultManagementError:
                raise
            except Exception:
                logger.exception("Blacklist rule creation failed")
                raise ResultManagementError("STATE_UNAVAILABLE", "规则无法保存。", 503) from None
        return row

    def change_rule(self, rule_id: str, expected_revision: int, data: dict | None) -> dict | None:
        rule_id = _uuid(rule_id)
        existing = next((row for row in self.rules() if row["id"] == rule_id), None)
        if existing is None:
            raise ResultManagementError("NOT_FOUND", "规则不存在。", 404)
        if existing["revision"] != expected_revision:
            raise ResultManagementError("REVISION_CONFLICT", "规则已改变，请刷新后重试。", 409)
        updated = {**existing, **(data or {}), "revision": expected_revision + 1,
                   "updated_at": datetime.now().astimezone().isoformat()}
        if self.local:
            def transform(records):
                for index, row in enumerate(records):
                    if row.get("id") == rule_id:
                        if row.get("revision") != expected_revision:
                            raise ResultManagementError("REVISION_CONFLICT", "规则已改变，请刷新后重试。", 409)
                        if data is None:
                            records.pop(index)
                        else:
                            records[index] = {**row, **updated}
                        return records
                raise ResultManagementError("NOT_FOUND", "规则不存在。", 404)
            self._local_mutate("blacklist_rules", transform)
        else:
            try:
                with self.storage.get_session() as session:
                    self._pg_version(session)
                    if data is None:
                        result = session.execute(text(
                            "DELETE FROM public.result_blacklist_rules "
                            "WHERE owner_id=:owner AND id=:id AND revision=:revision"),
                            {"owner": self.owner, "id": rule_id, "revision": expected_revision})
                    else:
                        result = session.execute(text(
                            "UPDATE public.result_blacklist_rules SET scope=:scope,task_ref=:task_ref,"
                            "task_name_snapshot=:task_name_snapshot,kind=:kind,pattern=:pattern,"
                            "enabled=:enabled,revision=revision+1,updated_at=CURRENT_TIMESTAMP "
                            "WHERE owner_id=:owner AND id=:id AND revision=:revision"),
                            {"owner": self.owner, "id": rule_id, "revision": expected_revision,
                             **{key: updated[key] for key in (
                                 "scope", "task_ref", "task_name_snapshot", "kind", "pattern", "enabled")}})
                    if result.rowcount != 1:
                        raise ResultManagementError("REVISION_CONFLICT", "规则已改变，请刷新后重试。", 409)
            except ResultManagementError:
                raise
            except Exception:
                logger.exception("Blacklist rule update failed")
                raise ResultManagementError("STATE_UNAVAILABLE", "规则无法更新。", 503) from None
        return updated if data is not None else None

    def preference(self) -> dict:
        if self.local:
            rows = self._local_read("view_preferences")
        else:
            rows = self._pg_rows(
                "SELECT page_key,task_ref,filters,sort_by,sort_order,revision,updated_at "
                "FROM public.result_view_preferences WHERE owner_id=:owner AND page_key='results'",
                {"owner": self.owner})
        return rows[0] if rows else {"page_key": "results", "task_ref": None,
                                    "filters": {}, "sort_by": "crawl_time", "sort_order": "desc",
                                    "revision": 0}

    def save_preference(self, data: dict, expected_revision: int) -> dict:
        current = self.preference()
        if current["revision"] != expected_revision:
            raise ResultManagementError("REVISION_CONFLICT", "筛选偏好已改变，请刷新后重试。", 409)
        updated = {"page_key": "results", "task_ref": data.get("task_ref"),
                   "filters": data["filters"], "sort_by": data["sort_by"],
                   "sort_order": data["sort_order"], "revision": expected_revision + 1,
                   "updated_at": datetime.now().astimezone().isoformat()}
        if self.local:
            def transform(records):
                if records and records[0].get("revision") != expected_revision:
                    raise ResultManagementError("REVISION_CONFLICT", "筛选偏好已改变，请刷新后重试。", 409)
                if not records and expected_revision != 0:
                    raise ResultManagementError("REVISION_CONFLICT", "筛选偏好已改变，请刷新后重试。", 409)
                return [{"owner_id": self.owner, **updated}]
            self._local_mutate("view_preferences", transform)
        else:
            try:
                with self.storage.get_session() as session:
                    self._pg_version(session)
                    params = {"owner": self.owner, "task_ref": updated["task_ref"],
                              "filters": json.dumps(updated["filters"], ensure_ascii=False),
                              "sort_by": updated["sort_by"], "sort_order": updated["sort_order"],
                              "expected": expected_revision}
                    if expected_revision == 0:
                        result = session.execute(text(
                            "INSERT INTO public.result_view_preferences "
                            "(owner_id,page_key,task_ref,filters,sort_by,sort_order,revision) "
                            "VALUES (:owner,'results',:task_ref,CAST(:filters AS jsonb),:sort_by,:sort_order,1) "
                            "ON CONFLICT DO NOTHING"), params)
                    else:
                        result = session.execute(text(
                            "UPDATE public.result_view_preferences SET task_ref=:task_ref,"
                            "filters=CAST(:filters AS jsonb),sort_by=:sort_by,sort_order=:sort_order,"
                            "revision=revision+1,updated_at=CURRENT_TIMESTAMP "
                            "WHERE owner_id=:owner AND page_key='results' AND revision=:expected"), params)
                    if result.rowcount != 1:
                        raise ResultManagementError("REVISION_CONFLICT", "筛选偏好已改变，请刷新后重试。", 409)
            except ResultManagementError:
                raise
            except Exception:
                logger.exception("Result preference update failed")
                raise ResultManagementError("STATE_UNAVAILABLE", "筛选偏好无法保存。", 503) from None
        return updated
