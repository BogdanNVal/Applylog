import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests_support import create_database_if_missing  # noqa: E402

PASSWORD = "test-password"

# CI sets APPLYLOG_TEST_DATABASE_URL; locally this hits docker-compose Postgres.
TEST_DSN = os.getenv(
    "APPLYLOG_TEST_DATABASE_URL",
    "postgresql://applylog:devpass@127.0.0.1:5433/applylog_test",
)


@pytest.fixture(scope="session", autouse=True)
def database():
    os.environ["APPLYLOG_DATABASE_URL"] = TEST_DSN
    create_database_if_missing(TEST_DSN)

    from app.db import close_pool, migrate

    migrate()
    yield
    close_pool()


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv("APPLYLOG_SECRET_KEY", "test-secret-key")

    from app.db import pool

    # Truncate is quicker than rebuilding the schema, and RESTART IDENTITY
    # keeps ids starting at 1 so tests can assume that.
    with pool().connection() as conn:
        conn.execute("TRUNCATE applications, users RESTART IDENTITY CASCADE")

    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def signed_in(app):
    test_client = TestClient(app)
    response = test_client.post(
        "/api/auth/register",
        json={"email": "first@example.com", "password": PASSWORD},
    )
    assert response.status_code == 201
    return test_client


@pytest.fixture()
def other_user(app):
    test_client = TestClient(app)
    response = test_client.post(
        "/api/auth/register",
        json={"email": "second@example.com", "password": PASSWORD},
    )
    assert response.status_code == 201
    return test_client
