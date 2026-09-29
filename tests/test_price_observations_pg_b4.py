"""B4 专用 PG15 合成库测试；只接受显式隔离库连接。"""

import os
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import event, text

from src.storage.postgres_adapter import PostgresAdapter
from src.storage.price_observations import PriceObservationRepository, summarize_market


@unittest.skipUnless(os.environ.get("QB_B4_TEST_DATABASE_URL"), "需要显式 B4 隔离合成库")
class PostgresPriceObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = os.environ["QB_B4_TEST_DATABASE_URL"]
        if url.rsplit("/", 1)[-1] != "qb_b4_price_20260929":
            raise RuntimeError("B4 PG test refuses a non-dedicated database")
        cls.storage = PostgresAdapter(url)

        @event.listens_for(cls.storage.engine, "connect")
        def restrict_connection(connection, _record):
            with connection.cursor() as cursor:
                cursor.execute("SET ROLE qb_b2_restored_app")
            connection.commit()

        with cls.storage.get_session() as session:
            if session.execute(text("SELECT current_user")).scalar_one() != "qb_b2_restored_app":
                raise RuntimeError("B4 PG test did not enter restricted role")
            if session.execute(text("SELECT version FROM public.app_schema_version")).scalar_one() != 2:
                raise RuntimeError("B4 PG test requires schema v2")
            owners = session.execute(text("SELECT id FROM public.users ORDER BY id")).fetchall()
            if len(owners) != 2:
                raise RuntimeError("B4 PG test requires two synthetic users")
            cls.owner_a, cls.owner_b = [str(row[0]) for row in owners]
            task = session.execute(text(
                "SELECT id FROM public.tasks WHERE owner_id=:owner LIMIT 1"
            ), {"owner": cls.owner_a}).first()
            if task is None:
                raise RuntimeError("B4 PG test requires one synthetic task for owner A")
            cls.task_ref = str(task[0])

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "storage"):
            cls.storage.engine.dispose()

    def test_restricted_role_idempotent_history_and_owner_isolation(self):
        first = PriceObservationRepository(self.storage, self.owner_a)
        second = PriceObservationRepository(self.storage, self.owner_b)
        item_id = "B4-" + uuid4().hex
        run_one, run_two = str(uuid4()), str(uuid4())
        self.assertTrue(first.append(task_ref=self.task_ref, task_name="合成任务",
                                     item_id=item_id, run_id=run_one, raw_price="¥100"))
        self.assertFalse(first.append(task_ref=self.task_ref, task_name="合成任务",
                                      item_id=item_id, run_id=run_one, raw_price="¥99"))
        self.assertTrue(first.append(task_ref=self.task_ref, task_name="改名后的合成任务",
                                     item_id=item_id, run_id=run_two, raw_price="¥80"))
        self.assertFalse(second.append(task_ref=self.task_ref, task_name="不属于本人",
                                       item_id=item_id, run_id=str(uuid4()), raw_price="¥70"))
        now = datetime.now(timezone.utc)
        window = {"since": now - timedelta(days=1), "until": now,
                  "task_ref": self.task_ref, "item_id": item_id}
        own_rows = first.list_observations(**window)
        self.assertEqual(len(own_rows), 2)
        self.assertEqual(len({row["task_name_snapshot"] for row in own_rows}), 1)
        self.assertEqual(second.list_observations(**window), [])
        self.assertEqual(summarize_market(own_rows)[0]["sample_count"], 1)
        self.assertEqual(list(first.iter_observations(
            since=window["since"], until=window["until"], task_ref=self.task_ref))[0]["item_id"], item_id)


if __name__ == "__main__":
    unittest.main()
