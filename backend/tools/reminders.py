from datetime import datetime
from typing import Any, Optional

from backend.database import (
    cancel_reminder,
    create_reminder,
    get_pending_reminders,
    get_reminders,
    get_timezone,
)


def _parse_remind_at(
    remind_at: str,
) -> datetime:

    value = (remind_at or "").strip()

    if not value:

        raise ValueError("remind_at is required.")

    if value.endswith("Z"):

        value = value[:-1] + "+00:00"

    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:

        parsed = parsed.replace(
            tzinfo=get_timezone()
        )

    return parsed.astimezone(get_timezone())


def tool_create_reminder(
    text: str,
    remind_at: str,
    user_id: str = "default",
) -> dict[str, Any]:

    try:

        remind_datetime = _parse_remind_at(remind_at)

        reminder = create_reminder(
            text=text,
            remind_at=remind_datetime,
            user_id=user_id,
        )

        return {
            "success": True,
            "reminder": reminder,
        }

    except ValueError as error:

        return {
            "success": False,
            "error": str(error),
        }

    except Exception as error:

        return {
            "success": False,
            "error": f"Could not create reminder: {error}",
        }


def tool_get_reminders(
    user_id: str = "default",
    pending_only: bool = True,
) -> dict[str, Any]:

    try:

        if pending_only:

            reminders = get_pending_reminders(user_id)

        else:

            reminders = get_reminders(user_id)

        return {
            "success": True,
            "reminders": reminders,
        }

    except Exception as error:

        return {
            "success": False,
            "error": f"Could not fetch reminders: {error}",
        }


def tool_cancel_reminder(
    user_id: str = "default",
    reminder_id: Optional[int] = None,
    text_match: Optional[str] = None,
) -> dict[str, Any]:

    try:

        return cancel_reminder(
            reminder_id=reminder_id,
            text_match=text_match,
            user_id=user_id,
        )

    except Exception as error:

        return {
            "success": False,
            "error": f"Could not cancel reminder: {error}",
        }
