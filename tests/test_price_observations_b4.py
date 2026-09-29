"""B4 价格观察：合成数据，不访问真实闲鱼或发送通知。"""

import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.storage.local_adapter import LocalStorageAdapter
from src.parsers import _parse_search_results_json
from src.storage.result_management import ResultManagementRepository
from src.storage.price_observations import (
    PriceObservationRepository, normalize_price, summarize_item, summarize_market,
)
from src.storage.upstream_local import LocalUpstreamStore
from src.web import price_observations, result_manager
from src.web.result_filters import ResultViewHttpError


TASK_REF = "82b6e47e-750d-4cc8-bfd0-b45a9be87011"
RUN_ONE = "082ba46d-2ee1-435d-befe-083371423bee"
RUN_TWO = "8f44c25b-66d3-48a4-80bf-8d49367e34c9"


class PriceDomainTests(unittest.TestCase):
    def test_csv_refuses_more_than_50000_visible_rows_before_response(self):
        closed = []
        class FakeRepo:
            def iter_observations(self, **_kwargs):
                try:
                    for _ in range(50001):
                        yield {"task_ref": TASK_REF, "item_id": "1"}
                finally:
                    closed.append(True)

        scope = (FakeRepo(), {(TASK_REF, "1")}, TASK_REF,
                 datetime.now(timezone.utc) - timedelta(days=1), datetime.now(timezone.utc))
        with patch.object(price_observations, "_scope", new=AsyncMock(return_value=scope)), \
             patch("src.web.auth.get_current_user", return_value={"user_id": "local_admin"}), \
             patch("src.web.auth.has_category", return_value=True):
            with self.assertRaises(ResultViewHttpError) as caught:
                asyncio.run(price_observations.export_prices(None))
        self.assertEqual(caught.exception.status_code, 429)
        self.assertTrue(closed)

    def test_search_parser_preserves_raw_price_for_observation(self):
        response = {"data": {"resultList": [{"data": {"item": {"main": {
            "exContent": {"title": "Xbox", "itemId": "123", "price": [{"text": "当前价"}, {"text": "¥1.2万"}]},
            "clickParam": {"args": {}}, "targetUrl": "https://example.test/?id=123"
        }}}}]}}
        items = asyncio.run(_parse_search_results_json(response, "合成测试"))
        self.assertEqual(items[0]["_搜索价格原文"], "¥1.2万")
        self.assertEqual(items[0]["当前售价"], "¥12000")

    def test_decimal_and_invalid_price(self):
        self.assertEqual(normalize_price("¥1.2万"), ("CNY", "¥1.2万", "12000.00"))
        self.assertEqual(normalize_price("¥1.234万"), ("CNY", "¥1.234万", "12340.00"))
        self.assertEqual(normalize_price("HK$1,234.50"), ("HKD", "HK$1,234.50", "1234.50"))
        for value in ("面议", "NaN", "1.234", "1.2345678万", "12,34", "-2", "1e10"):
            with self.subTest(value=value):
                self.assertIsNone(normalize_price(value)[2])

    def test_median_deduplicates_items_and_separates_currency(self):
        rows = []
        for item_id, amount, currency, observed_at in (
            ("1", "10.00", "CNY", "2026-09-01T00:00:00+00:00"),
            ("1", "20.00", "CNY", "2026-09-02T00:00:00+00:00"),
            ("2", "40.00", "CNY", "2026-09-02T00:00:00+00:00"),
            ("3", "90.00", "USD", "2026-09-02T00:00:00+00:00"),
        ):
            rows.append({"id": item_id + observed_at, "task_ref": TASK_REF,
                         "item_id": item_id, "amount": amount, "currency": currency,
                         "observed_at": observed_at})
        item = summarize_item(rows[:2])
        self.assertEqual(item["change_amount"], "10.00")
        self.assertEqual(item["lowest_amount"], "10.00")
        groups = summarize_market(rows)
        cny = next(group for group in groups if group["currency"] == "CNY")
        self.assertEqual(cny["sample_count"], 2)
        self.assertEqual(cny["median_amount"], "30.00")
        self.assertTrue(cny["reference_insufficient"])


class LocalPriceApiTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / ".tmp" / "tests" / "b4-price-observations"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="local-", dir=root)
        self.base = Path(self.temp.name)
        LocalUpstreamStore(self.base).initialize()
        self.storage = LocalStorageAdapter(str(self.base))
        self.repo = PriceObservationRepository(self.storage, "local_admin")
        (self.base / "config.json").write_text(json.dumps([
            {"task_name": "任务 A", "keyword": "xbox", "stable_task_id": TASK_REF}
        ], ensure_ascii=False), encoding="utf-8")
        self.result_file = self.base / "jsonl" / "任务_A_full_data.jsonl"
        self.result_file.write_text(json.dumps({
            "任务名称": "任务 A", "stable_task_id": TASK_REF,
            "商品信息": {"商品ID": "1", "商品链接": "https://example.com/?id=1",
                                          "商品标题": "Xbox 主机", "当前售价": "100"}
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        self.app = FastAPI()
        self.app.include_router(result_manager.router)
        self.app.include_router(price_observations.router)
        self.user = {"user_id": "local_admin", "username": "test"}

    def tearDown(self):
        self.temp.cleanup()

    def client_scope(self):
        return patch.multiple(
            "src.web.price_observations",
            get_storage=lambda: self.storage,
            get_current_user=lambda request: self.user,
        )

    def test_restart_dedup_window_and_http_owner_scope(self):
        self.assertTrue(self.repo.append(task_ref=TASK_REF, task_name="任务 A", item_id="1",
                                         run_id=RUN_ONE, raw_price="¥100"))
        self.assertFalse(PriceObservationRepository(self.storage, "local_admin").append(
            task_ref=TASK_REF, task_name="任务 A", item_id="1", run_id=RUN_ONE, raw_price="¥99"))
        self.assertTrue(self.repo.append(task_ref=TASK_REF, task_name="任务 A", item_id="1",
                                         run_id=RUN_TWO, raw_price="¥80"))
        now = datetime.now(timezone.utc)
        rows = self.repo.list_observations(since=now - timedelta(days=1), until=now)
        self.assertEqual(len(rows), 2)
        self.assertEqual(summarize_item(rows)["change_amount"], "-20.00")
        old_cwd = Path.cwd()
        try:
            os.chdir(self.base)
            with patch("src.web.auth.get_current_user", return_value=self.user), \
                 patch("src.web.auth.has_category", return_value=True), \
                 patch.object(result_manager, "get_current_user", return_value=self.user), \
                 patch.object(result_manager, "get_storage", return_value=self.storage), \
                 self.client_scope(), TestClient(self.app) as client:
                result = client.get("/api/results/all")
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.json()["items"][0]["price_observation"]["lowest_amount"], "80.00")
                history = client.get("/api/price-observations/items/1?limit=1")
                self.assertEqual(history.status_code, 200, history.text)
                self.assertEqual(len(history.json()["items"]), 1)
                cursor = history.json()["next_cursor"]
                self.assertIsNotNone(cursor)
                self.assertEqual(len(client.get(f"/api/price-observations/items/1?cursor={cursor}").json()["items"]), 1)
                summary = client.get("/api/price-observations/summary")
                self.assertEqual(summary.json()["groups"][0]["sample_count"], 1)
                self.assertTrue(summary.json()["groups"][0]["reference_insufficient"])
                self.assertEqual(client.get("/api/price-observations/items/2").status_code, 404)
                self.assertEqual(client.get("/api/price-observations/summary?task_ref=00000000-0000-0000-0000-000000000000").status_code, 404)
                self.assertEqual(client.get("/api/price-observations/summary?since=2020-01-01T00:00:00Z").status_code, 400)
        finally:
            os.chdir(old_cwd)

    def test_rename_keeps_history_and_csv_formula_is_safe(self):
        (self.base / "config.json").write_text(json.dumps([
            {"task_name": "=旧任务", "keyword": "xbox", "stable_task_id": TASK_REF}
        ], ensure_ascii=False), encoding="utf-8")
        self.repo.append(task_ref=TASK_REF, task_name="=旧任务", item_id="1",
                         run_id=RUN_ONE, raw_price="=1+2")
        (self.base / "config.json").write_text(json.dumps([
            {"task_name": "任务 B", "keyword": "xbox", "stable_task_id": TASK_REF}
        ], ensure_ascii=False), encoding="utf-8")
        old_cwd = Path.cwd()
        try:
            os.chdir(self.base)
            with patch("src.web.auth.get_current_user", return_value=self.user), \
                 patch("src.web.auth.has_category", return_value=True), \
                 patch.object(result_manager, "get_current_user", return_value=self.user), \
                 patch.object(result_manager, "get_storage", return_value=self.storage), \
                 self.client_scope(), TestClient(self.app) as client:
                self.assertEqual(client.get("/api/price-observations/items/1").status_code, 200)
                exported = client.get("/api/price-observations/export.csv")
                self.assertEqual(exported.status_code, 200, exported.text)
                self.assertIn("'=旧任务", exported.text)
                self.assertIn("'=1+2", exported.text)
                self.assertFalse(exported.content.startswith(b"\xef\xbb\xbf"))
                self.result_file.unlink()
                self.assertEqual(client.get("/api/price-observations/items/1").status_code, 404)
        finally:
            os.chdir(old_cwd)

    def test_hidden_filter_and_permission_are_shared(self):
        self.repo.append(task_ref=TASK_REF, task_name="任务 A", item_id="1",
                         run_id=RUN_ONE, raw_price="¥100")
        ResultManagementRepository(self.storage, "local_admin").set_hidden("1", True)
        old_cwd = Path.cwd()
        try:
            os.chdir(self.base)
            with patch("src.web.auth.get_current_user", return_value=self.user), \
                 patch("src.web.auth.has_category", return_value=True), \
                 patch.object(result_manager, "get_current_user", return_value=self.user), \
                 patch.object(result_manager, "get_storage", return_value=self.storage), \
                 self.client_scope(), TestClient(self.app) as client:
                self.assertEqual(client.get("/api/price-observations/summary").json()["groups"], [])
                self.assertEqual(client.get("/api/price-observations/items/1").status_code, 404)
                self.assertEqual(client.get("/api/price-observations/summary?include_hidden=true").json()["groups"][0]["sample_count"], 1)
                self.assertEqual(client.get("/api/price-observations/items/1?include_hidden=true").status_code, 200)
                self.assertNotIn("¥100", client.get("/api/price-observations/export.csv").text)
                with patch("src.web.auth.has_category", return_value=False):
                    self.assertEqual(client.get("/api/price-observations/summary").status_code, 403)
        finally:
            os.chdir(old_cwd)

    def test_deleted_task_cannot_append_or_rebind_same_name(self):
        self.repo.append(task_ref=TASK_REF, task_name="任务 A", item_id="1",
                         run_id=RUN_ONE, raw_price="100")
        replacement_ref = "f648e879-4007-4e76-90e0-a0c0e32271e2"
        (self.base / "config.json").write_text(json.dumps([
            {"task_name": "任务 A", "keyword": "xbox", "stable_task_id": replacement_ref}
        ], ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(Exception, "任务已不存在"):
            self.repo.append(task_ref=TASK_REF, task_name="任务 A", item_id="1",
                             run_id=RUN_TWO, raw_price="80")
        self.assertEqual(len(self.repo.list_observations(
            since=datetime.now(timezone.utc) - timedelta(days=1),
            until=datetime.now(timezone.utc))), 1)
        old_cwd = Path.cwd()
        try:
            os.chdir(self.base)
            with patch("src.web.auth.get_current_user", return_value=self.user), \
                 patch("src.web.auth.has_category", return_value=True), \
                 patch.object(result_manager, "get_current_user", return_value=self.user), \
                 patch.object(result_manager, "get_storage", return_value=self.storage), \
                 self.client_scope(), TestClient(self.app) as client:
                self.assertEqual(client.get("/api/price-observations/items/1").status_code, 404)
                self.assertEqual(client.get("/api/price-observations/summary").json()["groups"], [])
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
