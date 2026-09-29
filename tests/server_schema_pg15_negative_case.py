"""隔离 PG15 负向验收；只允许本轮固定的合成数据库。"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from scripts.upstream.migrate_server import verify_backup
from src.portable.schema_fingerprint import public_schema_fingerprint
from src.storage.server_migration import (
    LEGACY_PG15_FINGERPRINT, SERVER_V2_PG15_FINGERPRINT,
    ServerMigrationError, migrate_server_schema,
)


DATABASE = "qb_b2_negative"
ROLE = "qb_b2_negative_app"


def _expect_rejected(action) -> None:
    try:
        action()
    except ServerMigrationError:
        return
    raise AssertionError("server migration accepted an unsafe input")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--pg-restore", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("QB_TEST_PG15_NEGATIVE_ADMIN_URL", "")
    url = make_url(dsn)
    if (url.host != "127.0.0.1" or url.port != 59538
        or url.database != DATABASE or url.username != "qb_b2_admin"):
        raise RuntimeError("PG15 negative test target is not the approved synthetic database")
    backup = args.backup.resolve(strict=True)
    with backup.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    engine = create_engine(dsn, poolclass=NullPool)
    proof = lambda: verify_backup(backup, digest, args.pg_restore.resolve(strict=True), DATABASE)
    try:
        with engine.begin() as connection:
            assert public_schema_fingerprint(connection) == LEGACY_PG15_FINGERPRINT
            assert connection.execute(text(
                "SELECT 1 FROM pg_roles WHERE rolname = :role"
            ), {"role": ROLE}).scalar_one_or_none() is None

        _expect_rejected(lambda: verify_backup(
            backup, "0" * 64, args.pg_restore.resolve(strict=True), DATABASE
        ))
        _expect_rejected(lambda: verify_backup(
            backup, digest, args.pg_restore.resolve(strict=True), "wrong_database"
        ))

        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE public.b2_unknown_probe(id integer)"))
        try:
            _expect_rejected(lambda: migrate_server_schema(
                engine, expected_database=DATABASE, app_role=ROLE,
                app_password="B2SyntheticNegativeOnly-20260929-1",
                verify_quiesced=lambda: None, verify_backup=proof,
            ))
        finally:
            with engine.begin() as connection:
                connection.execute(text("DROP TABLE public.b2_unknown_probe"))

        calls = 0

        def fail_after_ddl() -> None:
            nonlocal calls
            calls += 1
            if calls == 3:
                raise ServerMigrationError("synthetic rollback injection")

        _expect_rejected(lambda: migrate_server_schema(
            engine, expected_database=DATABASE, app_role=ROLE,
            app_password="B2SyntheticNegativeOnly-20260929-1",
            verify_quiesced=fail_after_ddl, verify_backup=proof,
        ))
        assert calls == 3
        with engine.begin() as connection:
            assert public_schema_fingerprint(connection) == LEGACY_PG15_FINGERPRINT
            assert connection.execute(text(
                "SELECT to_regclass('public.app_schema_version')"
            )).scalar_one() is None
            assert connection.execute(text(
                "SELECT 1 FROM pg_roles WHERE rolname = :role"
            ), {"role": ROLE}).scalar_one_or_none() is None

        result = migrate_server_schema(
            engine, expected_database=DATABASE, app_role=ROLE,
            app_password="B2SyntheticNegativeOnly-20260929-1",
            verify_quiesced=lambda: None, verify_backup=proof,
        )
        assert result.status == "applied"
        assert migrate_server_schema(
            engine, expected_database=DATABASE, app_role=ROLE,
            app_password="B2SyntheticNegativeOnly-20260929-1",
            verify_quiesced=lambda: None, verify_backup=proof,
        ).status == "already_applied"
        with engine.begin() as connection:
            assert public_schema_fingerprint(connection) == SERVER_V2_PG15_FINGERPRINT
        print("SERVER_PG15_NEGATIVE_AND_ROLLBACK=PASS")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
