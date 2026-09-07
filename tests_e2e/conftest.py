"""Live server fixtures for browser tests."""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests_support import reset_database  # noqa: E402

STARTUP_TIMEOUT = 30

# Separate DB so e2e does not touch API test data.
E2E_DSN = os.getenv(
    "APPLYLOG_E2E_DATABASE_URL",
    "postgresql://applylog:devpass@127.0.0.1:5433/applylog_e2e",
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_healthy(base_url: str, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited early with code {process.returncode}")
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.2)
    raise RuntimeError(f"Server did not become healthy within {STARTUP_TIMEOUT}s")


@pytest.fixture(scope="session")
def live_server():
    reset_database(E2E_DSN)

    port = _free_port()
    # Server migrates on startup; empty DB is enough.
    env = {**os.environ, "APPLYLOG_DATABASE_URL": E2E_DSN}
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
    )

    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_until_healthy(base_url, process)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture(scope="session")
def base_url(live_server):
    """Base URL for page.goto("/")."""
    return live_server


@pytest.fixture()
def signed_in_page(page, base_url):
    """Page with a fresh account."""
    page.goto("/")
    page.get_by_role("tab", name="Create account").click()
    page.get_by_label("Email").fill(f"e2e-{uuid4().hex[:12]}@example.com")
    page.get_by_label("Password").fill("e2e-test-password")
    page.get_by_role("button", name="Create account").click()

    page.get_by_role("button", name="Add application").wait_for()
    return page
