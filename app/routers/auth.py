"""Auth: register, login, logout."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response, status
from psycopg.errors import UniqueViolation

from app.deps import SESSION_USER_KEY, Conn, CurrentUser
from app.schemas import Credentials, UserOut
from app.security import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

INVALID_CREDENTIALS = "Email or password is incorrect"


def _sign_in(request: Request, user_id: int) -> None:
    request.session.clear()
    request.session[SESSION_USER_KEY] = user_id


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: Credentials, request: Request, conn: Conn) -> UserOut:
    email = payload.email.lower()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        row = conn.execute(
            "INSERT INTO users (email, password_hash, created_at)"
            " VALUES (%s, %s, %s) RETURNING id",
            (email, hash_password(payload.password), now),
        ).fetchone()
    except UniqueViolation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user_id = int(row["id"])
    _sign_in(request, user_id)
    return UserOut(id=user_id, email=email, created_at=now)


@router.post("/login", response_model=UserOut)
def login(payload: Credentials, request: Request, conn: Conn) -> UserOut:
    row = conn.execute(
        "SELECT id, email, password_hash, created_at FROM users"
        " WHERE lower(email) = %s",
        (payload.email.lower(),),
    ).fetchone()

    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS
        )

    _sign_in(request, row["id"])
    return UserOut(id=row["id"], email=row["email"], created_at=row["created_at"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut(**user)
