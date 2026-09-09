from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from psycopg import Connection

from app.db import pool

SESSION_USER_KEY = "user_id"


def get_conn():
    with pool().connection() as conn:
        yield conn


Conn = Annotated[Connection, Depends(get_conn)]


def get_current_user(request: Request, conn: Conn) -> dict[str, Any]:
    user_id = request.session.get(SESSION_USER_KEY)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    row = conn.execute(
        "SELECT id, email, created_at FROM users WHERE id = %s", (user_id,)
    ).fetchone()
    if row is None:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return row


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]
