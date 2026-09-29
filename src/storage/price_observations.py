"""价格观察的规范化与持久化；不参与推荐、通知或抓取频率。"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from src.storage.local_adapter import LocalStorageAdapter
from src.storage.upstream_local import LocalUpstreamStateError


logger = logging.getLogger(__name__)
_PRICE_PATTERN = re.compile(r"^((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,6})?)(万)?$")
_MAX_AMOUNT = Decimal("999999999999.99")


class PriceObservationError(RuntimeError):
    """价格状态不可用；调用方可决定是否让非核心抓取继续。"""


def normalize_price(value: Any) -> tuple[str, str, str | None]:
    """返回币种、原文和可统计金额；无法确定的数字绝不猜成零。"""
    original = str(value if value is not None else "").strip()
    raw = original[:256]
    if not raw:
        return "UNKNOWN", raw, None
    if len(original) > 256:
        return "UNKNOWN", raw, None
    currency = "CNY"
    candidate = raw.replace(" ", "").replace("　", "")
    if candidate.startswith("HK$"):
        currency, candidate = "HKD", candidate[3:]
    elif candidate.startswith("US$"):
        currency, candidate = "USD", candidate[3:]
    elif candidate.startswith("$"):
        currency, candidate = "USD", candidate[1:]
    elif candidate.startswith(("¥", "￥")):
        candidate = candidate[1:]
    elif any(marker in candidate for marker in ("$", "¥", "￥")):
        return "UNKNOWN", raw, None
    if candidate.endswith("元"):
        candidate = candidate[:-1]
    match = _PRICE_PATTERN.fullmatch(candidate)
    if not match:
        return currency, raw, None
    try:
        amount = Decimal(match[1].replace(",", ""))
        if match[2]:
            amount *= 10000
        if (not amount.is_finite() or amount < 0 or amount > _MAX_AMOUNT
            or amount != amount.quantize(Decimal("0.01"))):
            return currency, raw, None
        return currency, raw, str(amount.quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError):
        return currency, raw, None


def _canonical_uuid(value: Any) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise PriceObservationError("价格观察缺少有效身份。") from None


def _validate_local_row(row: dict) -> datetime:
    try:
        _canonical_uuid(row["id"])
        _canonical_uuid(row["task_ref"])
        _canonical_uuid(row["run_id"])
        if (row.get("owner_id") != "local_admin"
            or not isinstance(row["item_id"], str) or not 1 <= len(row["item_id"]) <= 128
            or not isinstance(row["task_name_snapshot"], str)
            or len(row["task_name_snapshot"]) > 255
            or not isinstance(row["raw_price"], str) or len(row["raw_price"]) > 256
            or not isinstance(row["currency"], str) or len(row["currency"]) > 8
            or not isinstance(row["source"], str) or len(row["source"]) > 32):
            raise ValueError("shape")
        observed_at = datetime.fromisoformat(str(row["observed_at"]).replace("Z", "+00:00"))
        if observed_at.tzinfo is None or observed_at.utcoffset() != timedelta(0):
            raise ValueError("timestamp")
        if row.get("amount") is not None:
            amount = Decimal(str(row["amount"]))
            if (not amount.is_finite() or amount < 0 or amount > _MAX_AMOUNT
                or amount.as_tuple().exponent < -2):
                raise ValueError("amount")
        return observed_at
    except (KeyError, TypeError, ValueError, InvalidOperation, PriceObservationError):
        raise PriceObservationError("本地价格观察格式无效。") from None


class PriceObservationRepository:
    def __init__(self, storage: Any, owner_id: str):
        self.storage = storage
        self.local = isinstance(storage, LocalStorageAdapter)
        if self.local:
            if owner_id != "local_admin":
                raise PriceObservationError("本地价格观察身份无效。")
            self.owner = owner_id
        else:
            self.owner = _canonical_uuid(owner_id)

    def append(self, *, task_ref: str, task_name: str, item_id: str,
               run_id: str, raw_price: Any, source: str = "search") -> bool:
        """一次既有搜索响应的一件商品只写一次；跨运行另存一条。"""
        task_ref, run_id = _canonical_uuid(task_ref), _canonical_uuid(run_id)
        item_id = str(item_id or "").strip()
        if not item_id or len(item_id) > 128 or len(str(task_name)) > 255:
            raise PriceObservationError("价格观察商品或任务身份无效。")
        if self.local:
            try:
                current = next((task for task in self.storage.get_tasks(owner_id=self.owner)
                                if str(task.get("stable_task_id")) == task_ref), None)
            except Exception:
                logger.exception("本地价格观察任务身份核验失败")
                raise PriceObservationError("任务身份无法校验，本次价格不记录。") from None
            if current is None:
                raise PriceObservationError("任务已不存在，本次价格不记录。")
            task_name = str(current.get("task_name") or "")[:255]
        currency, raw, amount = normalize_price(raw_price)
        if not raw:
            return False
        observation = {
            "id": str(uuid4()), "owner_id": self.owner, "task_ref": task_ref,
            "task_name_snapshot": str(task_name), "item_id": item_id,
            "run_id": run_id, "observed_at": datetime.now(timezone.utc).isoformat(),
            "currency": currency, "raw_price": raw, "amount": amount,
            "source": source,
        }
        if self.local:
            try:
                return self.storage.upstream_store(owner_id=self.owner).append_price_observation(observation)
            except (LocalUpstreamStateError, PermissionError) as exc:
                logger.warning("本地价格观察写入失败", exc_info=exc)
                raise PriceObservationError("本地价格观察状态不可用。") from None
        try:
            with self.storage.get_session() as session:
                version = session.execute(text("SELECT version FROM public.app_schema_version LIMIT 2")).fetchall()
                if version != [(2,)]:
                    raise PriceObservationError("数据库尚未升级到 v2。")
                result = session.execute(text(
                    "INSERT INTO public.price_observations "
                    "(id,owner_id,task_ref,task_name_snapshot,item_id,run_id,observed_at,"
                    "currency,raw_price,amount,source) "
                    "SELECT :id,:owner_id,t.id,t.task_name,:item_id,:run_id,:observed_at,"
                    ":currency,:raw_price,:amount,:source FROM public.tasks t "
                    "WHERE t.id=:task_ref AND t.owner_id=:owner_id "
                    "ON CONFLICT (owner_id,task_ref,item_id,run_id) DO NOTHING"
                ), observation)
                return result.rowcount > 0
        except PriceObservationError:
            raise
        except Exception as exc:
            logger.exception("PostgreSQL 价格观察写入失败")
            raise PriceObservationError("价格观察数据库写入失败。") from None

    def list_observations(self, *, since: datetime, until: datetime,
                          task_ref: str | None = None, item_id: str | None = None,
                          limit: int = 50001) -> list[dict]:
        if task_ref is not None:
            task_ref = _canonical_uuid(task_ref)
        if not 1 <= limit <= 50001:
            raise PriceObservationError("价格观察读取上限无效。")
        if self.local:
            try:
                rows = self.storage.upstream_store(owner_id=self.owner).read_price_observations()
            except (LocalUpstreamStateError, PermissionError) as exc:
                logger.warning("本地价格观察读取失败", exc_info=exc)
                raise PriceObservationError("本地价格观察状态不可用。") from None
            result = []
            for row in rows:
                observed_at = _validate_local_row(row)
                if (since <= observed_at <= until
                    and (task_ref is None or row.get("task_ref") == task_ref)
                    and (item_id is None or row.get("item_id") == item_id)):
                    result.append(row)
            result.sort(key=lambda row: (row["observed_at"], row["id"]), reverse=True)
            return result[:limit]
        try:
            with self.storage.get_session() as session:
                version = session.execute(text("SELECT version FROM public.app_schema_version LIMIT 2")).fetchall()
                if version != [(2,)]:
                    raise PriceObservationError("数据库尚未升级到 v2。")
                conditions = ["owner_id=:owner", "observed_at>=:since", "observed_at<=:until"]
                params = {"owner": self.owner, "since": since, "until": until, "limit": limit}
                if task_ref is not None:
                    conditions.append("task_ref=:task_ref")
                    params["task_ref"] = task_ref
                if item_id is not None:
                    conditions.append("item_id=:item_id")
                    params["item_id"] = item_id
                rows = session.execute(text(
                    "SELECT id,owner_id,task_ref,task_name_snapshot,item_id,run_id,observed_at,"
                    "currency,raw_price,amount,source FROM public.price_observations "
                    "WHERE " + " AND ".join(conditions) + " "
                    "ORDER BY observed_at DESC,id DESC LIMIT :limit"
                ), params).mappings().all()
                return [{key: (value.isoformat() if isinstance(value, datetime) else str(value)
                         if isinstance(value, (UUID, Decimal)) else value)
                         for key, value in dict(row).items()} for row in rows]
        except PriceObservationError:
            raise
        except Exception:
            logger.exception("PostgreSQL 价格观察读取失败")
            raise PriceObservationError("价格观察数据库读取失败。") from None

    def iter_observations(self, *, since: datetime, until: datetime,
                          task_ref: str | None = None):
        """导出专用流式读取；调用方须在取消时 close()。"""
        if task_ref is not None:
            task_ref = _canonical_uuid(task_ref)
        if self.local:
            source = None
            try:
                source = self.storage.upstream_store(owner_id=self.owner).iter_price_observations()
                for row in source:
                    observed_at = _validate_local_row(row)
                    if (since <= observed_at <= until
                        and (task_ref is None or row["task_ref"] == task_ref)):
                        yield row
            except (LocalUpstreamStateError, PermissionError) as exc:
                logger.warning("本地价格观察流式读取失败", exc_info=exc)
                raise PriceObservationError("本地价格观察状态不可用。") from None
            finally:
                if source is not None:
                    source.close()
            return
        try:
            with self.storage.get_session() as session:
                version = session.execute(text("SELECT version FROM public.app_schema_version LIMIT 2")).fetchall()
                if version != [(2,)]:
                    raise PriceObservationError("数据库尚未升级到 v2。")
                conditions = ["owner_id=:owner", "observed_at>=:since", "observed_at<=:until"]
                params = {"owner": self.owner, "since": since, "until": until}
                if task_ref is not None:
                    conditions.append("task_ref=:task_ref")
                    params["task_ref"] = task_ref
                result = session.execute(text(
                    "SELECT id,owner_id,task_ref,task_name_snapshot,item_id,run_id,observed_at,"
                    "currency,raw_price,amount,source FROM public.price_observations "
                    "WHERE " + " AND ".join(conditions) + " ORDER BY observed_at DESC,id DESC"
                ).execution_options(stream_results=True), params).mappings()
                for mapping in result:
                    row = dict(mapping)
                    yield {key: (value.isoformat() if isinstance(value, datetime) else str(value)
                                 if isinstance(value, (UUID, Decimal)) else value)
                           for key, value in row.items()}
        except PriceObservationError:
            raise
        except Exception:
            logger.exception("PostgreSQL 价格观察流式读取失败")
            raise PriceObservationError("价格观察数据库读取失败。") from None


def summarize_item(rows: list[dict]) -> dict:
    """只比较同一商品同一币种的有效观察，不把异常原文当作零。"""
    ordered = sorted(rows, key=lambda row: (row["observed_at"], row["id"]))
    if not ordered:
        return {"observation_count": 0, "first_observed_at": None,
                "last_observed_at": None, "currency": None, "lowest_amount": None,
                "highest_amount": None, "latest_amount": None, "change_amount": None}
    valid = [row for row in ordered if row.get("amount") is not None]
    latest_currency = valid[-1]["currency"] if valid else None
    comparable = [row for row in valid if row["currency"] == latest_currency]
    amounts = [Decimal(str(row["amount"])) for row in comparable]
    change = amounts[-1] - amounts[-2] if len(amounts) >= 2 else None
    return {
        "observation_count": len(ordered),
        "first_observed_at": ordered[0]["observed_at"],
        "last_observed_at": ordered[-1]["observed_at"],
        "currency": latest_currency,
        "lowest_amount": str(min(amounts)) if amounts else None,
        "highest_amount": str(max(amounts)) if amounts else None,
        "latest_amount": str(amounts[-1]) if amounts else None,
        "change_amount": str(change) if change is not None else None,
    }


def summarize_market(rows: list[dict]) -> list[dict]:
    """每个任务/币种/商品只取窗口内最后一条有效观察。"""
    latest: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        if row.get("amount") is None:
            continue
        key = (row["task_ref"], row["currency"], row["item_id"])
        if key not in latest or (row["observed_at"], row["id"]) > (
                latest[key]["observed_at"], latest[key]["id"]):
            latest[key] = row
    groups: dict[tuple[str, str], list[Decimal]] = {}
    for (task_ref, currency, _), row in latest.items():
        groups.setdefault((task_ref, currency), []).append(Decimal(str(row["amount"])))
    return [{"task_ref": task_ref, "currency": currency,
             "sample_count": len(amounts), "median_amount": str(median(amounts)),
             "reference_insufficient": len(amounts) < 5,
             "label": "本人该任务采样参考",
             "comparability_note": "不同规格或成色可能不可比，仅供参考。"}
            for (task_ref, currency), amounts in sorted(groups.items())]
