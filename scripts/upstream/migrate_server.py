"""显式升级 PostgreSQL 15 服务器旧库；普通 Web 启动不调用本命令。"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
from time import monotonic

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from src.portable.backup_archive import _assert_no_reparse_ancestry
from src.portable.schema_catalog import V1_TABLE_COLUMNS
from src.storage.server_migration import ServerMigrationError, migrate_server_schema


_CONFIRMATION = "我已停止所有连接此数据库的业务进程"
_MAX_DUMP_BYTES = 1024 ** 4
_MAX_TOC_BYTES = 4 * 1024 * 1024


def verify_backup(path: Path, digest: str, pg_restore: Path, expected_database: str) -> None:
    """核验已完成的 PG15 自定义格式备份；不把 TOC 误称为恢复演练。"""
    if (not path.is_absolute() or not pg_restore.is_absolute()
        or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise ServerMigrationError("server backup proof is invalid")
    try:
        _assert_no_reparse_ancestry(path, Path(path.anchor))
        _assert_no_reparse_ancestry(pg_restore, Path(pg_restore.anchor))
        if not path.is_file() or not pg_restore.is_file():
            raise ServerMigrationError("server backup or verification tool is missing")
        size = path.stat().st_size
        if not 1 <= size <= _MAX_DUMP_BYTES:
            raise ServerMigrationError("server backup size is invalid")
        observed = hashlib.sha256()
        with path.open("rb") as stream:
            if stream.read(5) != b"PGDMP":
                raise ServerMigrationError("server backup format is invalid")
            stream.seek(0)
            while block := stream.read(1024 * 1024):
                observed.update(block)
        if observed.hexdigest() != digest:
            raise ServerMigrationError("server backup digest differs")
        deadline = monotonic() + 60
        process = subprocess.Popen(
            [str(pg_restore), "--list", str(path)], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        reader = ThreadPoolExecutor(max_workers=1)
        try:
            try:
                toc_bytes = reader.submit(process.stdout.read, _MAX_TOC_BYTES + 1).result(
                    timeout=max(0.1, deadline - monotonic())
                )
            except FutureTimeoutError:
                raise ServerMigrationError("server backup TOC verification timed out") from None
            if len(toc_bytes) > _MAX_TOC_BYTES:
                raise ServerMigrationError("server backup TOC exceeds the safety limit")
            returncode = process.wait(timeout=max(0.1, deadline - monotonic()))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            reader.shutdown(wait=True)
            process.stdout.close()
        if returncode != 0:
            raise ServerMigrationError("server backup TOC could not be verified")
        toc = toc_bytes.decode("utf-8", errors="strict")
        database = re.search(r"^;\s+dbname: (\S+)\s*$", toc, flags=re.MULTILINE)
        version = re.search(r"^;\s+Dumped from database version: (\d+)\.", toc,
                            flags=re.MULTILINE)
        tables = set(re.findall(r"^\d+;\s+\d+\s+\d+\s+TABLE public (\S+)\s+",
                                toc, flags=re.MULTILINE))
        if (database is None or database.group(1) != expected_database
            or version is None or version.group(1) != "15"
            or tables != set(V1_TABLE_COLUMNS)):
            raise ServerMigrationError("server backup TOC differs from the legacy database")
    except ServerMigrationError:
        raise
    except Exception:
        raise ServerMigrationError("server backup could not be verified safely") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-name", required=True)
    parser.add_argument("--app-role", required=True)
    parser.add_argument("--backup", required=True, type=Path)
    parser.add_argument("--backup-sha256", required=True)
    parser.add_argument("--pg-restore", required=True, type=Path)
    parser.add_argument("--confirm-stopped", required=True)
    args = parser.parse_args(argv)
    if args.confirm_stopped != _CONFIRMATION:
        parser.error("停写确认不匹配；升级未开始")
    admin_dsn = os.environ.get("QB_SERVER_ADMIN_DATABASE_URL")
    app_password = os.environ.get("QB_SERVER_APP_PASSWORD")
    if not admin_dsn or not app_password:
        print("服务器升级凭据未配置；升级未开始。", file=sys.stderr)
        return 2
    engine = None
    try:
        url = make_url(admin_dsn)
        if url.drivername not in ("postgresql", "postgresql+psycopg2") or url.database != args.database_name:
            raise ServerMigrationError("server database URL differs from the selected target")
        def backup_proof() -> None:
            verify_backup(args.backup, args.backup_sha256, args.pg_restore,
                          args.database_name)
        def maintenance_proof() -> None:
            # The process stop is an operator action; the migration transaction
            # independently checks sessions and takes exclusive table locks.
            if args.confirm_stopped != _CONFIRMATION:
                raise ServerMigrationError("server writer stop was not confirmed")
        engine = create_engine(admin_dsn, poolclass=NullPool, connect_args={"connect_timeout": 5})
        result = migrate_server_schema(
            engine, expected_database=args.database_name, app_role=args.app_role,
            app_password=app_password, verify_quiesced=maintenance_proof,
            verify_backup=backup_proof,
        )
        print(f"服务器 schema v{result.version} 已核验：{result.status}。")
        return 0
    except Exception:
        print("服务器 schema 升级未确认成功；原备份保留，请停止操作并检查。", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                print("服务器数据库连接清理失败。", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
