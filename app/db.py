from __future__ import annotations

import os
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"

# Same default as docker-compose.yml.
DEFAULT_DSN = "postgresql://applylog:devpass@127.0.0.1:5433/applylog"

_pool: ConnectionPool | None = None
_pool_dsn: str | None = None


def dsn() -> str:
    # Read at call time so tests can swap APPLYLOG_DATABASE_URL.
    return os.getenv("APPLYLOG_DATABASE_URL", DEFAULT_DSN)


def pool() -> ConnectionPool:
    # Autocommit because FastAPI closes a yield dep *after* the response goes
    # out. I used to commit in teardown; the browser's next request beat it
    # and signup looked like it immediately logged you out.
    # Use conn.transaction() if you need more than one statement to be atomic.
    global _pool, _pool_dsn
    target = dsn()
    if _pool is not None and _pool_dsn != target:
        close_pool()
    if _pool is None:
        _pool = ConnectionPool(
            target,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row, "autocommit": True},
            # Neon/Render drop idle connections; ping before reuse.
            check=ConnectionPool.check_connection,
            open=True,
        )
        _pool_dsn = target
    return _pool


def close_pool() -> None:
    global _pool, _pool_dsn
    if _pool is not None:
        _pool.close()
        _pool = None
        _pool_dsn = None


def migrate() -> None:
    with pool().connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version text PRIMARY KEY,"
            " applied_at timestamptz NOT NULL DEFAULT now())"
        )
        applied = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations")
        }

    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.stem in applied:
            continue
        # Don't record the version unless the SQL actually ran.
        with pool().connection() as conn, conn.transaction():
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,)
            )
