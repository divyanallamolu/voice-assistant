import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


DEFAULT_TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
IST_FALLBACK = timezone(timedelta(hours=5, minutes=30))
DB_PATH = os.getenv(
    "JARVIS_DB_PATH",
    os.path.join(
        os.path.dirname(__file__),
        "data",
        "jarvis.db",
    ),
)


def get_timezone():

    if ZoneInfo is None:
        return IST_FALLBACK

    try:

        return ZoneInfo(DEFAULT_TIMEZONE)

    except Exception:

        return IST_FALLBACK


def now_local() -> datetime:

    return datetime.now(get_timezone())


def _connect() -> sqlite3.Connection:

    os.makedirs(
        os.path.dirname(DB_PATH),
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_db() -> None:

    with _connect() as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'default'
            )
            """
        )

        connection.commit()


def create_reminder(
    text: str,
    remind_at: datetime,
    user_id: str = "default",
) -> dict[str, Any]:

    created_at = now_local().isoformat()

    remind_at_value = (
        remind_at.astimezone(get_timezone()).isoformat()
    )

    with _connect() as connection:

        cursor = connection.execute(
            """
            INSERT INTO reminders (
                text,
                remind_at,
                status,
                created_at,
                user_id
            )
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (
                text.strip(),
                remind_at_value,
                created_at,
                user_id,
            ),
        )

        connection.commit()

        reminder_id = cursor.lastrowid

    return get_reminder_by_id(reminder_id)


def get_reminder_by_id(
    reminder_id: int,
) -> Optional[dict[str, Any]]:

    with _connect() as connection:

        row = connection.execute(
            """
            SELECT *
            FROM reminders
            WHERE id = ?
            """,
            (reminder_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def get_reminders(
    user_id: str = "default",
    status: Optional[str] = None,
) -> list[dict[str, Any]]:

    query = """
        SELECT *
        FROM reminders
        WHERE user_id = ?
    """

    params: list[Any] = [user_id]

    if status is not None:

        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY remind_at ASC"

    with _connect() as connection:

        rows = connection.execute(
            query,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def get_pending_reminders(
    user_id: Optional[str] = None,
) -> list[dict[str, Any]]:

    query = """
        SELECT *
        FROM reminders
        WHERE status = 'pending'
    """

    params: list[Any] = []

    if user_id is not None:

        query += " AND user_id = ?"
        params.append(user_id)

    query += " ORDER BY remind_at ASC"

    with _connect() as connection:

        rows = connection.execute(
            query,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def get_due_reminders() -> list[dict[str, Any]]:

    current_time = now_local().isoformat()

    with _connect() as connection:

        rows = connection.execute(
            """
            SELECT *
            FROM reminders
            WHERE status = 'pending'
              AND remind_at <= ?
            ORDER BY remind_at ASC
            """,
            (current_time,),
        ).fetchall()

    return [dict(row) for row in rows]


def mark_reminder_triggered(
    reminder_id: int,
) -> Optional[dict[str, Any]]:

    with _connect() as connection:

        connection.execute(
            """
            UPDATE reminders
            SET status = 'triggered'
            WHERE id = ?
              AND status = 'pending'
            """,
            (reminder_id,),
        )

        connection.commit()

    return get_reminder_by_id(reminder_id)


def mark_reminder_completed(
    reminder_id: int,
) -> Optional[dict[str, Any]]:

    with _connect() as connection:

        connection.execute(
            """
            UPDATE reminders
            SET status = 'completed'
            WHERE id = ?
            """,
            (reminder_id,),
        )

        connection.commit()

    return get_reminder_by_id(reminder_id)


def cancel_reminder(
    reminder_id: Optional[int] = None,
    text_match: Optional[str] = None,
    user_id: str = "default",
) -> dict[str, Any]:

    if reminder_id is not None:

        with _connect() as connection:

            connection.execute(
                """
                UPDATE reminders
                SET status = 'cancelled'
                WHERE id = ?
                  AND user_id = ?
                  AND status = 'pending'
                """,
                (reminder_id, user_id),
            )

            connection.commit()

        reminder = get_reminder_by_id(reminder_id)

        if reminder is None:
            return {
                "success": False,
                "message": "Reminder not found.",
            }

        return {
            "success": True,
            "reminder": reminder,
        }

    if text_match:

        pending = get_pending_reminders(user_id)

        lowered = text_match.lower()

        matches = [
            item
            for item in pending
            if lowered in item["text"].lower()
        ]

        if not matches:
            return {
                "success": False,
                "message": "No matching pending reminder found.",
            }

        if len(matches) > 1:
            return {
                "success": False,
                "message": "Multiple reminders matched. Please be more specific.",
                "matches": matches,
            }

        reminder_id = matches[0]["id"]

        with _connect() as connection:

            connection.execute(
                """
                UPDATE reminders
                SET status = 'cancelled'
                WHERE id = ?
                """,
                (reminder_id,),
            )

            connection.commit()

        return {
            "success": True,
            "reminder": get_reminder_by_id(reminder_id),
        }

    return {
        "success": False,
        "message": "Provide reminder_id or text_match.",
    }
