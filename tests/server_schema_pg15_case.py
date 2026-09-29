"""隔离 PostgreSQL 15 服务器 v2 运行态验收；只接受固定合成目标。"""

from __future__ import annotations

import os
import sys
from types import ModuleType
from unittest import mock

import psycopg2
from psycopg2 import errors
from sqlalchemy.engine import make_url


_DATABASE = "qb_b2_legacy"
_FIRST = "11111111-1111-4111-8111-111111111111"
_SECOND = "22222222-2222-4222-8222-222222222222"


def _safe_dsn(name: str, user: str) -> str:
    dsn = os.environ.get(name, "")
    url = make_url(dsn)
    if url.host != "127.0.0.1" or url.database != _DATABASE or url.username != user:
        raise RuntimeError("PG15 acceptance target is not the approved synthetic database")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _query(dsn: str, statement: str, parameters: tuple = ()):
    connection = psycopg2.connect(dsn)
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            rows = cursor.fetchall() if cursor.description else []
        connection.commit()
        return rows
    finally:
        connection.close()


def _expect_denied(dsn: str, statement: str) -> None:
    try:
        _query(dsn, statement)
    except errors.InsufficientPrivilege:
        return
    raise AssertionError("restricted app role unexpectedly accepted forbidden SQL")


def main() -> int:
    admin_dsn = _safe_dsn("QB_TEST_PG15_ADMIN_URL", "qb_b2_admin")
    app_dsn = _safe_dsn("QB_TEST_PG15_APP_URL", "qb_b2_app")
    assert _query(app_dsn, "SELECT version FROM public.app_schema_version") == [(2,)]
    assert _query(app_dsn, "SELECT rolsuper, rolcreatedb, rolcreaterole, "
                  "rolreplication, rolbypassrls FROM pg_roles "
                  "WHERE rolname = current_user") == [(False,) * 5]
    assert _query(app_dsn, "SELECT has_database_privilege("
                  "current_user, current_database(), 'CREATE')") == [(False,)]
    _expect_denied(app_dsn, "CREATE TABLE public.forbidden_b2_ddl(id integer)")
    _expect_denied(app_dsn, "SELECT migration_id FROM public.app_schema_migrations")
    _query(app_dsn, "INSERT INTO public.result_hidden_items(owner_id,item_id) "
           "VALUES (%s,'synthetic-a-item'),(%s,'synthetic-b-item') "
           "ON CONFLICT DO NOTHING", (_FIRST, _SECOND))

    fake_config = ModuleType("src.config")
    fake_config.PORTABLE_MODE = False
    fake_config.WEB_USERNAME = lambda: "synthetic-admin"
    fake_config.WEB_PASSWORD = lambda: "SyntheticOnly-DoNotUse-20260929"
    with mock.patch.dict(sys.modules, {"src.config": fake_config}):
        from src.storage.postgres_adapter import PostgresAdapter
        app = PostgresAdapter(app_dsn)
        admin = PostgresAdapter(admin_dsn)
        try:
            try:
                admin.create_tables()
            except RuntimeError as error:
                if "DDL privileges" not in str(error):
                    raise
            else:
                raise AssertionError("administrator was accepted as the v2 Web role")
            app.create_tables()
            first = app.list_upstream_records("result_hidden_items", owner_id=_FIRST)
            second = app.list_upstream_records("result_hidden_items", owner_id=_SECOND)
            assert {row["item_id"] for row in first} == {"synthetic-a-item"}
            assert {row["item_id"] for row in second} == {"synthetic-b-item"}
        finally:
            app.engine.dispose()
            admin.engine.dispose()
    print("SERVER_PG15_V2_RUNTIME=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
