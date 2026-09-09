"""Dump a handful of fake applications into an existing account.

    python scripts/seed_demo.py --email you@example.com [--reset]

Sign up in the app first — this script doesn't touch passwords.
"""

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import close_pool, migrate, pool  # noqa: E402

SAMPLES = [
    (2, "Northwind Labs", "Junior Backend Developer", "Remote", "interview",
     "Referred by a friend. Take-home task expected next week."),
    (4, "Contoso Retail", "Graduate Software Engineer", "Manchester", "applied",
     "Applied through their careers page."),
    (6, "Blue Harbour", "QA Engineer (Entry)", "Remote", "rejected",
     "Rejected after the screening call - no automation experience."),
    (9, "Fabrikam", "Junior Python Developer", "Dublin", "offer",
     "Offer received. Starts next month."),
    (12, "Tailwind Traders", "Data Analyst Intern", "London", "applied",
     "Recruiter said they review applications every two weeks."),
    (15, "Adventure Works", "Junior Full-Stack Developer", "Remote", "rejected",
     "Automated rejection email."),
    (18, "Litware", "Associate Software Engineer", "Berlin", "interview",
     "Second interview scheduled with the team lead."),
    (22, "Proseware", "Junior Developer (PHP)", "Remote", "applied",
     "Long shot - stack does not match well."),
]


def seed(email: str, reset: bool) -> None:
    migrate()
    with pool().connection() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE lower(email) = %s", (email.lower(),)
        ).fetchone()
        if row is None:
            sys.exit(f"No account found for {email}. Sign up in the app first.")

        user_id = row["id"]
        if reset:
            conn.execute("DELETE FROM applications WHERE user_id = %s", (user_id,))

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        today = date.today()
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO applications"
                " (user_id, company, role, link, location, notes, status, applied_on,"
                "  created_at, updated_at)"
                " VALUES (%s, %s, %s, '', %s, %s, %s, %s, %s, %s)",
                [
                    (
                        user_id,
                        company,
                        role,
                        location,
                        notes,
                        status,
                        (today - timedelta(days=days_ago)).isoformat(),
                        now,
                        now,
                    )
                    for days_ago, company, role, location, status, notes in SAMPLES
                ],
            )

    close_pool()
    print(f"Seeded {len(SAMPLES)} applications for {email}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Email of an existing account")
    parser.add_argument(
        "--reset", action="store_true", help="Wipe this account's applications first"
    )
    args = parser.parse_args()
    seed(args.email, args.reset)
