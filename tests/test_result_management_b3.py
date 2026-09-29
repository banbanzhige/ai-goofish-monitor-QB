"""B3 隔离合成验收：视图过滤与本地 v2 持久化。"""

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.storage.local_adapter import LocalStorageAdapter
from src.storage.result_management import ResultManagementError, ResultManagementRepository
from src.storage.upstream_local import LocalUpstreamStore
from src.web.result_filters import InvalidRule, apply_view_rules, rule_matches, validate_rule
from src.web import result_manager
from src.web import result_management


TASK_REF = "82b6e47e-750d-4cc8-bfd0-b45a9be87011"


def record(item_id, title, task="任务 A"):
    return {"任务名称": task, "商品信息": {"商品链接": f"https://item.example/?id={item_id}",
                                       "商品标题": title, "商品描述": "描述"}}


class RuleFilterTests(unittest.TestCase):
    def test_literal_alias_and_word_boundary(self):
        alias = {"kind": "regex_alias", "pattern": "Xbox|XSX", "scope": "global", "enabled": True}
        self.assertTrue(rule_matches(record("1", "二手 xsx 主机"), alias, TASK_REF))
        word = {"kind": "word", "pattern": "Xbox", "scope": "global", "enabled": True}
        self.assertTrue(rule_matches(record("1", "Xbox 主机"), word, TASK_REF))
        self.assertFalse(rule_matches(record("2", "Xboxer 主机"), word, TASK_REF))
        self.assertFalse(rule_matches(record("3", "Xbox 主机"), {**word, "scope": "task", "task_ref": TASK_REF}, None))

    def test_unsupported_regex_rejected_without_execution(self):
        for pattern in ("(a+)+", "a.*b", "[a-z]", "a||b", "\\w+", "x" * 129):
            with self.subTest(pattern=pattern), self.assertRaises(InvalidRule):
                validate_rule("regex_alias", pattern)

    def test_filter_before_page_and_statistics(self):
        rows = [record("1", "正常"), record("2", "屏蔽"), record("3", "Xbox"), record("4", "可见")]
        rules = [{"id": "rule", "kind": "keyword", "pattern": "Xbox", "enabled": True, "scope": "global"}]
        visible, stats = apply_view_rules(rows, {"2"}, rules, result_manager._extract_item_id,
                                          lambda item: TASK_REF)
        self.assertEqual([result_manager._extract_item_id(item) for item in visible[:2]], ["1", "4"])
        self.assertEqual(stats, {"total_items": 2, "hidden_count": 1, "blacklist_count": 1})
        with_hidden, stats = apply_view_rules(rows, {"2"}, rules, result_manager._extract_item_id,
                                              lambda item: TASK_REF, include_hidden=True)
        self.assertEqual(len(with_hidden), 4)
        self.assertTrue(with_hidden[1]["view_hidden"])
        self.assertEqual(with_hidden[2]["blacklist_reasons"][0]["rule_id"], "rule")


class LocalRepositoryTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / ".tmp" / "tests" / "b3-result-management"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="local-", dir=root)
        base = Path(self.temp.name)
        LocalUpstreamStore(base).initialize()
        self.storage = LocalStorageAdapter(str(base))
        self.repo = ResultManagementRepository(self.storage, "local_admin")

    def tearDown(self):
        self.temp.cleanup()

    def test_hidden_idempotent_and_persistent(self):
        self.repo.set_hidden("123", True)
        self.repo.set_hidden("123", True)
        self.assertEqual(len(ResultManagementRepository(self.storage, "local_admin").hidden_items()), 1)
        self.repo.set_hidden("123", False)
        self.repo.set_hidden("123", False)
        self.assertEqual(self.repo.hidden_items(), [])

    def test_rule_revision_and_preference_revision(self):
        rule = self.repo.create_rule({"scope": "global", "task_ref": None,
                                      "task_name_snapshot": None, "kind": "keyword",
                                      "pattern": "无人机", "enabled": True})
        changed = self.repo.change_rule(rule["id"], 1, {"enabled": False})
        self.assertEqual(changed["revision"], 2)
        with self.assertRaises(ResultManagementError) as caught:
            self.repo.change_rule(rule["id"], 1, {"enabled": True})
        self.assertEqual(caught.exception.status, 409)
        self.repo.change_rule(rule["id"], 2, None)
        self.assertEqual(self.repo.rules(), [])
        preference = self.repo.save_preference({"task_ref": None, "filters": {"include_hidden": True},
                                                "sort_by": "price", "sort_order": "asc"}, 0)
        self.assertEqual(preference["revision"], 1)
        self.assertEqual(self.repo.preference()["filters"], {"include_hidden": True})
        with self.assertRaises(ResultManagementError) as caught:
            self.repo.save_preference({"task_ref": None, "filters": {},
                                       "sort_by": "price", "sort_order": "asc"}, 0)
        self.assertEqual(caught.exception.status, 409)

    def test_owner_rejected(self):
        with self.assertRaises(ResultManagementError):
            ResultManagementRepository(self.storage, "other")

    def test_http_list_pagination_export_and_legacy_delete(self):
        base = Path(self.temp.name)
        (base / "config.json").write_text(json.dumps([
            {"task_name": "任务 A", "keyword": "xbox", "stable_task_id": TASK_REF}
        ], ensure_ascii=False), encoding="utf-8")
        results = [record("1", "正常一"), record("2", "正常二"), record("3", "Xbox 主机")]
        (base / "jsonl" / "任务_A_full_data.jsonl").write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in results) + "\n",
            encoding="utf-8")
        app = FastAPI()
        app.include_router(result_manager.router)
        app.include_router(result_management.router)
        user = {"user_id": "local_admin", "username": "test"}
        previous = Path.cwd()
        try:
            os.chdir(base)
            with patch("src.web.auth.get_current_user", return_value=user), \
                 patch("src.web.auth.has_category", return_value=True), \
                 patch.object(result_manager, "get_current_user", return_value=user), \
                 patch.object(result_management, "get_current_user", return_value=user), \
                 patch.object(result_manager, "get_storage", return_value=self.storage), \
                 patch.object(result_management, "get_storage", return_value=self.storage), \
                 TestClient(app) as client:
                baseline = client.get("/api/results/all?limit=1&page=1")
                self.assertEqual(baseline.status_code, 200)
                self.assertEqual(baseline.json()["total_items"], 3)
                self.assertEqual(client.put("/api/result-management/hidden-items/2").status_code, 200)
                page_one = client.get("/api/results/all?limit=1&page=1").json()
                page_two = client.get("/api/results/all?limit=1&page=2").json()
                self.assertEqual(page_one["total_items"], 2)
                self.assertEqual(result_manager._extract_item_id(page_one["items"][0]), "1")
                self.assertEqual(result_manager._extract_item_id(page_two["items"][0]), "3")
                exported = client.get("/api/result-management/export.csv?filename=all")
                self.assertEqual(exported.status_code, 200)
                self.assertNotIn("正常二", exported.text)
                shown = client.get("/api/results/all?include_hidden=true").json()
                self.assertEqual(shown["total_items"], 3)
                self.assertTrue(next(item for item in shown["items"] if result_manager._extract_item_id(item) == "2")["view_hidden"])
                preview = client.post("/api/result-management/blacklist-rules/preview", json={
                    "scope": "task", "task_ref": TASK_REF, "kind": "keyword",
                    "pattern": "Xbox", "filename": "all"})
                self.assertEqual(preview.status_code, 200)
                self.assertEqual(preview.json()["sampled"], 3)
                self.assertEqual(preview.json()["matched"], 1)
                self.assertEqual(client.get("/api/result-management/blacklist-rules").json()["items"], [])
                rule = client.post("/api/result-management/blacklist-rules", json={
                    "expected_revision": 0, "scope": "task", "task_ref": TASK_REF,
                    "kind": "keyword", "pattern": "Xbox"})
                self.assertEqual(rule.status_code, 201)
                self.assertEqual(client.get("/api/results/all").json()["total_items"], 1)
                self.assertNotIn("Xbox 主机", client.get("/api/result-management/export.csv?filename=all").text)
                self.assertEqual(client.delete("/api/result-management/hidden-items/2").status_code, 200)
                self.assertEqual(client.get("/api/results/all").json()["total_items"], 2)
                old_delete = client.post("/api/results/delete-batch", json={
                    "filename": "all", "item_ids": ["2"], "filters": {}})
                self.assertEqual(old_delete.status_code, 200)
                self.assertEqual(old_delete.json()["deleted_count"], 1)
                self.assertEqual(client.get("/api/results/all").json()["total_items"], 1)
        finally:
            os.chdir(previous)

    def test_api_hidden_preference_and_rejection(self):
        app = FastAPI()
        app.include_router(result_management.router)
        user = {"user_id": "local_admin", "username": "test"}
        with patch("src.web.auth.get_current_user", return_value=user), \
             patch("src.web.auth.has_category", return_value=True), \
             patch.object(result_management, "get_current_user", return_value=user), \
             patch.object(result_management, "get_storage", return_value=self.storage), \
             TestClient(app) as client:
            self.assertEqual(client.put("/api/result-management/hidden-items/123").status_code, 200)
            self.assertEqual(client.put("/api/result-management/hidden-items/123").status_code, 200)
            self.assertEqual(len(client.get("/api/result-management/hidden-items").json()["items"]), 1)
            self.assertEqual(client.delete("/api/result-management/hidden-items/123").status_code, 200)
            response = client.post("/api/result-management/blacklist-rules", json={
                "expected_revision": 0, "scope": "global", "kind": "regex_alias", "pattern": "(x+)+"})
            self.assertEqual(response.status_code, 400)
            response = client.post("/api/result-management/blacklist-rules", json={
                "expected_revision": 0, "scope": "global", "kind": "regex_alias", "pattern": "Xbox|XSX"})
            self.assertEqual(response.status_code, 201)
            rule = response.json()
            self.assertEqual(len(client.get("/api/result-management/blacklist-rules").json()["items"]), 1)
            response = client.patch(f"/api/result-management/blacklist-rules/{rule['id']}", json={
                "expected_revision": 1, "enabled": False})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["revision"], 2)
            self.assertEqual(client.patch(f"/api/result-management/blacklist-rules/{rule['id']}", json={
                "expected_revision": 1, "enabled": True}).status_code, 409)
            self.assertEqual(client.delete(
                f"/api/result-management/blacklist-rules/{rule['id']}?expected_revision=2").status_code, 200)
            response = client.put("/api/result-management/view-preferences", json={
                "expected_revision": 0, "task_ref": None, "filters": {"include_hidden": True},
                "sort_by": "price", "sort_order": "asc"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["revision"], 1)
            self.assertEqual(client.put("/api/result-management/view-preferences", json={
                "expected_revision": 0, "task_ref": None, "filters": {},
                "sort_by": "price", "sort_order": "asc"}).status_code, 409)


class ResultQueryTests(unittest.TestCase):
    def test_query_and_export_share_view(self):
        source = [record("1", "普通"), record("2", "Xbox"), record("3", "普通三")]
        class FakeRepository:
            def __init__(self, storage, owner):
                pass
            def view_state(self):
                return {"1"}, [{"id": "rule", "kind": "keyword", "pattern": "Xbox",
                                 "scope": "global", "enabled": True}]
        async def load(filename, owner, storage):
            return source, [{"task_name": "任务 A", "stable_task_id": TASK_REF}]
        class Request:
            pass
        with patch.object(result_manager, "get_storage", return_value=object()), \
             patch.object(result_manager, "_get_owner_id", return_value=None), \
             patch.object(result_manager, "get_current_user", return_value={"user_id": "local_admin"}), \
             patch.object(result_manager, "ResultManagementRepository", FakeRepository), \
             patch.object(result_manager, "_load_results_for_view", load):
            view = asyncio.run(result_manager._query_result_view(
                "all", Request(), recommended_only=False, task_name="all", keyword="all",
                ai_criteria="all", sort_by="crawl_time", sort_order="desc",
                manual_keyword=None, include_hidden=False))
        self.assertEqual(view[1]["total_items"], 1)
        self.assertEqual(result_manager._extract_item_id(view[0][0]), "3")
        self.assertEqual(view[4]["task_names"], ["任务 A"])

    def test_csv_export_uses_query_view_and_escapes_formula(self):
        app = FastAPI()
        app.include_router(result_manager.router)
        user = {"user_id": "local_admin", "username": "test"}
        async def fake_query(*_args, **_kwargs):
            return [record("1", "=IMPORTXML('x')")], {"total_items": 1}, [], None, {}
        with patch("src.web.auth.get_current_user", return_value=user), \
             patch("src.web.auth.has_category", return_value=True), \
             patch.object(result_manager, "_query_result_view", fake_query), \
             TestClient(app) as client:
            response = client.get("/api/result-management/export.csv?filename=all")
        self.assertEqual(response.status_code, 200)
        self.assertIn("'=IMPORTXML", response.text)


if __name__ == "__main__":
    unittest.main()
