"""Application CRUD, filters, stats, CSV export."""

import csv
import io
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Response, status
from psycopg import Connection

from app.deps import Conn, CurrentUser
from app.schemas import STATUSES, ApplicationIn, ApplicationOut, Stats, Status

router = APIRouter(prefix="/api/applications", tags=["applications"])

COLUMNS = (
    "id, company, role, link, location, notes, status, applied_on, "
    "created_at, updated_at"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _escape_like(term: str) -> str:
    for char in ("\\", "%", "_"):
        term = term.replace(char, f"\\{char}")
    return term


def _query_applications(
    conn: Connection,
    user_id: int,
    status_filter: Optional[str],
    search: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
) -> list[dict[str, Any]]:
    sql = f"SELECT {COLUMNS} FROM applications WHERE user_id = %s"
    params: list[Any] = [user_id]

    if status_filter:
        sql += " AND status = %s"
        params.append(status_filter)

    if search:
        # ILIKE: Postgres LIKE is case-sensitive.
        sql += (
            " AND (company ILIKE %s ESCAPE '\\' OR role ILIKE %s ESCAPE '\\'"
            " OR location ILIKE %s ESCAPE '\\' OR notes ILIKE %s ESCAPE '\\')"
        )
        pattern = f"%{_escape_like(search.strip())}%"
        params.extend([pattern] * 4)

    if date_from:
        sql += " AND applied_on >= %s"
        params.append(date_from.isoformat())

    if date_to:
        sql += " AND applied_on <= %s"
        params.append(date_to.isoformat())

    sql += " ORDER BY applied_on DESC, id DESC"
    return conn.execute(sql, params).fetchall()


def _get_owned(conn: Connection, user_id: int, app_id: int) -> dict[str, Any]:
    row = conn.execute(
        f"SELECT {COLUMNS} FROM applications WHERE id = %s AND user_id = %s",
        (app_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        )
    return row


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    user: CurrentUser,
    conn: Conn,
    status_filter: Optional[Status] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None, alias="q", max_length=120),
    date_from: Optional[date] = Query(default=None, alias="from"),
    date_to: Optional[date] = Query(default=None, alias="to"),
) -> list[dict[str, Any]]:
    return _query_applications(
        conn, user["id"], status_filter, search, date_from, date_to
    )


@router.get("/stats", response_model=Stats)
def get_stats(user: CurrentUser, conn: Conn) -> Stats:
    counts = {name: 0 for name in STATUSES}
    for row in conn.execute(
        "SELECT status, COUNT(*) AS n FROM applications WHERE user_id = %s"
        " GROUP BY status",
        (user["id"],),
    ):
        counts[row["status"]] = row["n"]

    total = sum(counts.values())
    answered = total - counts["applied"]
    week_ago = (date.today() - timedelta(days=6)).isoformat()
    last_7_days = conn.execute(
        "SELECT COUNT(*) AS n FROM applications WHERE user_id = %s AND applied_on >= %s",
        (user["id"], week_ago),
    ).fetchone()["n"]

    return Stats(
        total=total,
        **counts,
        response_rate=round(answered / total * 100, 1) if total else 0.0,
        offer_rate=round(counts["offer"] / total * 100, 1) if total else 0.0,
        last_7_days=last_7_days,
    )


@router.get("/export.csv", response_class=Response)
def export_csv(
    user: CurrentUser,
    conn: Conn,
    status_filter: Optional[Status] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None, alias="q", max_length=120),
    date_from: Optional[date] = Query(default=None, alias="from"),
    date_to: Optional[date] = Query(default=None, alias="to"),
) -> Response:
    rows = _query_applications(
        conn, user["id"], status_filter, search, date_from, date_to
    )

    buffer = io.StringIO()
    fields = ["company", "role", "status", "applied_on", "location", "link", "notes"]
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

    filename = f"applylog-{date.today().isoformat()}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationIn, user: CurrentUser, conn: Conn
) -> dict[str, Any]:
    now = _now()
    return conn.execute(
        "INSERT INTO applications"
        " (user_id, company, role, link, location, notes, status, applied_on,"
        "  created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        f" RETURNING {COLUMNS}",
        (
            user["id"],
            payload.company,
            payload.role,
            payload.link,
            payload.location,
            payload.notes,
            payload.status,
            payload.applied_on.isoformat(),
            now,
            now,
        ),
    ).fetchone()


@router.get("/{app_id}", response_model=ApplicationOut)
def get_application(app_id: int, user: CurrentUser, conn: Conn) -> dict[str, Any]:
    return _get_owned(conn, user["id"], app_id)


@router.put("/{app_id}", response_model=ApplicationOut)
def update_application(
    app_id: int, payload: ApplicationIn, user: CurrentUser, conn: Conn
) -> dict[str, Any]:
    # Owner check + update in one statement.
    row = conn.execute(
        "UPDATE applications SET company = %s, role = %s, link = %s, location = %s,"
        " notes = %s, status = %s, applied_on = %s, updated_at = %s"
        " WHERE id = %s AND user_id = %s"
        f" RETURNING {COLUMNS}",
        (
            payload.company,
            payload.role,
            payload.link,
            payload.location,
            payload.notes,
            payload.status,
            payload.applied_on.isoformat(),
            _now(),
            app_id,
            user["id"],
        ),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        )
    return row


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(app_id: int, user: CurrentUser, conn: Conn) -> Response:
    row = conn.execute(
        "DELETE FROM applications WHERE id = %s AND user_id = %s RETURNING id",
        (app_id, user["id"]),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
