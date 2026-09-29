"""B3 的可选隔离 PG15 集成测试；只接受专用合成库连接。"""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import event, text

from src.storage.postgres_adapter import PostgresAdapter
from src.storage.result_management import ResultManagementError, ResultManagementRepository


@unittest.skipUnless(os.environ.get("QB_B3_TEST_DATABASE_URL"), "需要显式 B3 隔离合成库")
class PostgresResultManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.environ["QB_B3_TEST_DATABASE_URL"]
        if not cls.url.rsplit("/", 1)[-1] == "qb_b3_result":
            raise RuntimeError("B3 PG test refuses a non-dedicated database")
        cls.storage = PostgresAdapter(cls.url)
        @event.listens_for(cls.storage.engine, "connect")
        def restrict_connection(dbapi_connection, _record):
            with dbapi_connection.cursor() as cursor:
                cursor.execute("SET ROLE qb_b2_restored_app")
            dbapi_connection.commit()
        with cls.storage.get_session() as session:
            role = session.execute(text("SELECT current_user")).scalar_one()
            if role != "qb_b2_restored_app":
                raise RuntimeError("B3 PG test did not enter the restricted fixture role")
            rows = session.execute(text("SELECT id FROM public.users ORDER BY id LIMIT 2")).fetchall()
            if len(rows) != 2:
                raise RuntimeError("B3 PG test requires exactly two synthetic fixture users")
            cls.owner_a, cls.owner_b = map(lambda row: str(row[0]), rows)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "storage"):
            cls.storage.engine.dispose()

    def test_hidden_rule_preference_and_owner_isolation(self):
        first = ResultManagementRepository(self.storage, self.owner_a)
        second = ResultManagementRepository(self.storage, self.owner_b)
        item_id = "999" + uuid4().hex[:20]
        first.set_hidden(item_id, True)
        first.set_hidden(item_id, True)
        self.assertIn(item_id, {row["item_id"] for row in first.hidden_items()})
        self.assertNotIn(item_id, {row["item_id"] for row in second.hidden_items()})
        hidden, rules = first.view_state()
        self.assertIn(item_id, hidden)
        self.assertIsInstance(rules, list)
        first.set_hidden(item_id, False)
        first.set_hidden(item_id, False)

        marker = "B3-" + uuid4().hex[:12]
        rule = first.create_rule({"scope": "global", "task_ref": None,
                                  "task_name_snapshot": None, "kind": "keyword",
                                  "pattern": marker, "enabled": True})
        self.assertEqual(rule["revision"], 1)
        self.assertNotIn(rule["id"], {row["id"] for row in second.rules()})
        changed = first.change_rule(rule["id"], 1, {"enabled": False})
        self.assertEqual(changed["revision"], 2)
        with self.assertRaises(ResultManagementError) as caught:
            first.change_rule(rule["id"], 1, {"enabled": True})
        self.assertEqual(caught.exception.status, 409)
        with self.assertRaises(ResultManagementError) as caught:
            second.change_rule(rule["id"], 2, None)
        self.assertEqual(caught.exception.status, 404)
        first.change_rule(rule["id"], 2, None)

        current = first.preference()
        updated = first.save_preference({"task_ref": None, "filters": {"include_hidden": True},
                                         "sort_by": "price", "sort_order": "asc"}, current["revision"])
        self.assertEqual(updated["revision"], current["revision"] + 1)
        self.assertNotEqual(first.preference(), second.preference())
        with self.assertRaises(ResultManagementError) as caught:
            first.save_preference({"task_ref": None, "filters": {},
                                   "sort_by": "price", "sort_order": "asc"}, current["revision"])
        self.assertEqual(caught.exception.status, 409)

        # 两个并发页面拿到同一修订号时，只能有一个成功提交。
        revision = first.preference()["revision"]
        def compete(value):
            try:
                first.save_preference({"task_ref": None, "filters": {"manual_keyword": value},
                                       "sort_by": "crawl_time", "sort_order": "desc"}, revision)
                return "saved"
            except ResultManagementError as exc:
                return exc.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(compete, ("one", "two")))
        self.assertCountEqual(outcomes, ("saved", 409))


if __name__ == "__main__":
    unittest.main()
