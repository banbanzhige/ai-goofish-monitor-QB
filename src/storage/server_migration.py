"""Explicit PostgreSQL 15 server migration from the legacy unversioned schema.

This is deliberately separate from the Launcher-owned PostgreSQL 17 migration.
The caller must stop all application writers and verify a restorable backup;
ordinary Web startup never invokes this module.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.portable.schema_catalog import V1_TABLE_COLUMNS, V2_BUSINESS_TABLES
from src.portable.schema_fingerprint import public_schema_fingerprint
from src.portable.upstream_ddl import CREATE_STATEMENTS, MIGRATION_CHECKSUM, MIGRATION_ID, ddl_checksum


logger = logging.getLogger(__name__)
LEGACY_PG15_FINGERPRINT = "5edb41dc39eb076e5c40bb311bd5b6e0d27bdd76cd5b58ea1c5c75c2144e3592"
SERVER_V2_PG15_FINGERPRINT = "82da3dd4e28459a5e14102a3d5594836b026df038ba088d5e25ab5d6a1461366"
_ROLE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_LOCK_KEY = 0x27474F4F46495348


class ServerMigrationError(RuntimeError):
    """Migration refused or failed without exposing database credentials."""


@dataclass(frozen=True)
class ServerMigrationResult:
    version: int
    status: str


def _role_name(value: str) -> str:
    if (not isinstance(value, str) or not _ROLE_PATTERN.fullmatch(value)
        or value.lower() in {"current_role", "current_user", "none", "public", "session_user"}):
        raise ServerMigrationError("application role name is invalid")
    return value


def _assert_admin_and_target(connection, expected_database: str) -> None:
    major = int(connection.execute(text("SHOW server_version_num")).scalar_one()) // 10000
    if major != 15:
        raise ServerMigrationError("server migration requires PostgreSQL 15")
    database = connection.execute(text("SELECT current_database()")).scalar_one()
    if database != expected_database:
        raise ServerMigrationError("server migration database identity differs")
    role = connection.execute(text(
        "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
    )).scalar_one()
    if role is not True:
        raise ServerMigrationError("server migration requires an administrator")
    unknown = connection.execute(text(
        "SELECT nspname FROM pg_namespace "
        "WHERE nspname NOT IN ('public', 'information_schema') "
        "AND nspname NOT LIKE 'pg\\_%' ESCAPE '\\' LIMIT 1"
    )).scalar_one_or_none()
    if unknown is not None:
        raise ServerMigrationError("database contains an unknown application schema")


def _assert_no_other_clients(connection) -> None:
    count = connection.execute(text(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
        "AND pid <> pg_backend_pid() AND backend_type = 'client backend'"
    )).scalar_one()
    if count:
        raise ServerMigrationError("other database clients are still connected")


def _version(connection) -> int | None:
    if connection.execute(text("SELECT to_regclass('public.app_schema_version')")).scalar_one() is None:
        return None
    rows = connection.execute(text("SELECT version FROM public.app_schema_version LIMIT 2")).fetchall()
    if rows not in ([(2,)],):
        raise ServerMigrationError("server schema version is unsupported or damaged")
    return 2


def _assert_app_role(connection, app_role: str) -> None:
    flags = connection.execute(text(
        "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
        "FROM pg_roles WHERE rolname = :role"
    ), {"role": app_role}).one_or_none()
    if flags is None or tuple(flags) != (True, False, False, False, False, False):
        raise ServerMigrationError("application role attributes differ")
    if connection.execute(text(
        "SELECT has_schema_privilege(:role, 'public', 'CREATE')"
    ), {"role": app_role}).scalar_one():
        raise ServerMigrationError("application role has schema DDL permission")
    if connection.execute(text(
        "SELECT has_database_privilege(:role, current_database(), 'CREATE')"
    ), {"role": app_role}).scalar_one():
        raise ServerMigrationError("application role has database DDL permission")
    for table in sorted(V1_TABLE_COLUMNS.keys() | V2_BUSINESS_TABLES):
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            if not connection.execute(text(
                "SELECT has_table_privilege(:role, :table, :privilege)"
            ), {"role": app_role, "table": "public." + table,
                "privilege": privilege}).scalar_one():
                raise ServerMigrationError("application role is missing a business grant")
    if not connection.execute(text(
        "SELECT has_table_privilege(:role, 'public.app_schema_version', 'SELECT')"
    ), {"role": app_role}).scalar_one():
        raise ServerMigrationError("application role cannot read schema version")
    for table in ("app_schema_version", "app_schema_migrations"):
        for privilege in ("INSERT", "UPDATE", "DELETE"):
            if connection.execute(text(
                "SELECT has_table_privilege(:role, :table, :privilege)"
            ), {"role": app_role, "table": "public." + table,
                "privilege": privilege}).scalar_one():
                raise ServerMigrationError("application role can change schema metadata")
    if connection.execute(text(
        "SELECT has_table_privilege(:role, 'public.app_schema_migrations', 'SELECT')"
    ), {"role": app_role}).scalar_one():
        raise ServerMigrationError("application role can read migration audit")


def _assert_v2(connection, app_role: str) -> None:
    if public_schema_fingerprint(connection) != SERVER_V2_PG15_FINGERPRINT:
        raise ServerMigrationError("server v2 schema fingerprint differs")
    rows = connection.execute(text(
        "SELECT migration_id, checksum FROM public.app_schema_migrations LIMIT 2"
    )).fetchall()
    if rows != [(MIGRATION_ID, MIGRATION_CHECKSUM)]:
        raise ServerMigrationError("server migration record differs")
    _assert_app_role(connection, app_role)


def migrate_server_schema(
    engine: Engine, *, expected_database: str, app_role: str, app_password: str,
    verify_quiesced: Callable[[], None], verify_backup: Callable[[], None],
) -> ServerMigrationResult:
    """Apply or verify v2 under one transaction and an exclusive legacy-table lock."""
    app_role = _role_name(app_role)
    if (not isinstance(expected_database, str) or not expected_database
        or not isinstance(app_password, str) or not 16 <= len(app_password) <= 256
        or not callable(verify_quiesced) or not callable(verify_backup)):
        raise ServerMigrationError("server migration safety inputs are invalid")
    if ddl_checksum() != MIGRATION_CHECKSUM:
        raise ServerMigrationError("server migration DDL checksum differs")
    try:
        verify_quiesced()
        verify_backup()
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL search_path = pg_catalog, public"))
            connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _LOCK_KEY})
            _assert_admin_and_target(connection, expected_database)
            _assert_no_other_clients(connection)
            if _version(connection) == 2:
                _assert_v2(connection, app_role)
                verify_quiesced()
                verify_backup()
                return ServerMigrationResult(2, "already_applied")
            if public_schema_fingerprint(connection) != LEGACY_PG15_FINGERPRINT:
                raise ServerMigrationError("legacy server schema fingerprint differs")
            role_exists = connection.execute(text(
                "SELECT 1 FROM pg_roles WHERE rolname = :role"
            ), {"role": app_role}).scalar_one_or_none()
            if role_exists is not None:
                raise ServerMigrationError("new application role already exists")
            tables = ", ".join('public."' + table + '"' for table in sorted(V1_TABLE_COLUMNS))
            connection.execute(text("LOCK TABLE " + tables + " IN ACCESS EXCLUSIVE MODE"))
            _assert_no_other_clients(connection)
            verify_quiesced()
            verify_backup()
            connection.execute(text(
                'CREATE ROLE "' + app_role + '" LOGIN PASSWORD :password '
                'NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS'
            ), {"password": app_password})
            for statement in CREATE_STATEMENTS:
                connection.execute(text(statement))
            connection.execute(text(
                "CREATE TABLE public.app_schema_version "
                "(version integer PRIMARY KEY CHECK (version = 2))"
            ))
            connection.execute(text("INSERT INTO public.app_schema_version VALUES (2)"))
            connection.execute(text(
                "INSERT INTO public.app_schema_migrations (migration_id, checksum) "
                "VALUES (:migration_id, :checksum)"
            ), {"migration_id": MIGRATION_ID, "checksum": MIGRATION_CHECKSUM})
            connection.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
            connection.execute(text('GRANT USAGE ON SCHEMA public TO "' + app_role + '"'))
            business = ", ".join('public."' + table + '"'
                                 for table in sorted(V1_TABLE_COLUMNS.keys() | V2_BUSINESS_TABLES))
            connection.execute(text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE " + business +
                ' TO "' + app_role + '"'
            ))
            connection.execute(text(
                'GRANT SELECT ON TABLE public.app_schema_version TO "' + app_role + '"'
            ))
            _assert_v2(connection, app_role)
            verify_quiesced()
            verify_backup()
            return ServerMigrationResult(2, "applied")
    except ServerMigrationError:
        raise
    except Exception:
        logger.error("Server schema migration failed safely",
                     extra={"event": "server_schema_migration_failed"})
        raise ServerMigrationError("server schema migration failed safely") from None
