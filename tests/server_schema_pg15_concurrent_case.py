"""隔离 PG15 并发迁移验收；只允许本轮固定合成库。"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
from threading import Barrier

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from scripts.upstream.migrate_server import verify_backup
from src.portable.schema_fingerprint import public_schema_fingerprint
from src.storage.server_migration import (
    LEGACY_PG15_FINGERPRINT, SERVER_V2_PG15_FINGERPRINT,
    ServerMigrationError, migrate_server_schema,
)


DATABASE = "qb_b2_concurrent"
ROLE = "qb_b2_concurrent_app"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--pg-restore", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("QB_TEST_PG15_CONCURRENT_ADMIN_URL", "")
    url = make_url(dsn)
    if (url.host != "127.0.0.1" or url.port != 59538
        or url.database != DATABASE or url.username != "qb_b2_admin"):
        raise RuntimeError("PG15 concurrent test target is not the approved synthetic database")
    backup = args.backup.resolve(strict=True)
    pg_restore = args.pg_restore.resolve(strict=True)
    with backup.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    barrier = Barrier(2)

    def backup_proof() -> None:
        verify_backup(backup, digest, pg_restore, DATABASE)

    def worker() -> str:
        engine = create_engine(dsn, poolclass=NullPool)
        first = True

        def quiesced() -> None:
            nonlocal first
            if first:
                first = False
                barrier.wait(timeout=10)

        try:
            result = migrate_server_schema(
                engine, expected_database=DATABASE, app_role=ROLE,
                app_password="B2SyntheticConcurrentOnly-20260929-1",
                verify_quiesced=quiesced, verify_backup=backup_proof,
            )
            return result.status
        except ServerMigrationError:
            return "safely_rejected"
        finally:
            engine.dispose()

    engine = create_engine(dsn, poolclass=NullPool)
    try:
        with engine.begin() as connection:
            assert public_schema_fingerprint(connection) == LEGACY_PG15_FINGERPRINT
            assert connection.execute(text(
                "SELECT 1 FROM pg_roles WHERE rolname = :role"
            ), {"role": ROLE}).scalar_one_or_none() is None
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: worker(), range(2)))
        assert outcomes.count("applied") <= 1, outcomes
        assert set(outcomes) <= {"applied", "already_applied", "safely_rejected"}, outcomes
        # A simultaneous second client is deliberately refused. Once it exits,
        # a single retry must either apply the transaction or verify the winner.
        final = migrate_server_schema(
            engine, expected_database=DATABASE, app_role=ROLE,
            app_password="B2SyntheticConcurrentOnly-20260929-1",
            verify_quiesced=lambda: None, verify_backup=backup_proof,
        )
        assert final.status in {"applied", "already_applied"}
        with engine.begin() as connection:
            assert public_schema_fingerprint(connection) == SERVER_V2_PG15_FINGERPRINT
        print("SERVER_PG15_CONCURRENT=PASS")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
