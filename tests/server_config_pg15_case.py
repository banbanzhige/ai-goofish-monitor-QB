"""隔离 PG15 容器内的运行 DSN 优先级验收。"""

from sqlalchemy.engine import make_url

from src.config import DATABASE_URL, PORTABLE_MODE


def main() -> int:
    url = make_url(DATABASE_URL())
    if (PORTABLE_MODE or url.host != "127.0.0.1" or url.port != 5432
        or url.database != "qb_b2_legacy" or url.username != "qb_b2_app"):
        raise AssertionError("container runtime did not select the restricted app DSN")
    print("SERVER_PG15_CONTAINER_APP_DSN=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
