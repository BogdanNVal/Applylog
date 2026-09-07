"""Helpers shared by the API and browser test suites."""

import time

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

CONNECT_TIMEOUT = 30


def _connect_when_ready(conninfo: str) -> psycopg.Connection:
    """Retry until Postgres accepts connections (docker compose startup race)."""
    deadline = time.monotonic() + CONNECT_TIMEOUT
    while True:
        try:
            return psycopg.connect(conninfo, autocommit=True)
        except psycopg.OperationalError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)


def create_database_if_missing(dsn: str) -> None:
    """Create the DSN database if missing (via the postgres maintenance DB)."""
    parts = conninfo_to_dict(dsn)
    name = parts.pop("dbname")
    with _connect_when_ready(make_conninfo(**parts, dbname="postgres")) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
        ).fetchone()
        if not exists:
            # Name is from our config, not user input.
            conn.execute(f'CREATE DATABASE "{name}"')


def reset_database(dsn: str) -> None:
    """Wipe schema so a run starts empty."""
    create_database_if_missing(dsn)
    with _connect_when_ready(dsn) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
