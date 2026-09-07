"""ApplyLog application entry point."""

import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.db import close_pool, migrate
from app.routers import applications, auth

STATIC_DIR = Path(__file__).resolve().parent / "static"
SESSION_MAX_AGE = 14 * 24 * 60 * 60


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate()
    yield
    close_pool()


app = FastAPI(
    title="ApplyLog API",
    description="Track job applications, statuses and response rates.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("APPLYLOG_SECRET_KEY", secrets.token_hex(32)),
    session_cookie="applylog_session",
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=os.getenv("APPLYLOG_HTTPS_ONLY", "0") == "1",
)

app.include_router(auth.router)
app.include_router(applications.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
