import asyncio
import json
from typing import Any, Optional

from backend.database import get_due_reminders, mark_reminder_triggered


CHECK_INTERVAL_SECONDS = 5

active_connections: dict[str, Any] = {}


def register_connection(
    session_id: str,
    websocket: Any,
) -> None:

    active_connections[session_id] = websocket


def unregister_connection(
    session_id: str,
) -> None:

    active_connections.pop(session_id, None)


async def _deliver_reminder(
    reminder: dict[str, Any],
) -> None:

    session_id = reminder.get("user_id")

    websocket = active_connections.get(session_id)

    payload = json.dumps({
        "type": "reminder",
        "text": f"Reminder: {reminder['text']}",
        "reminder_id": reminder["id"],
    })

    if websocket is not None:

        try:

            await websocket.send_text(payload)

            print(
                "⏰ Reminder delivered:",
                reminder["text"],
                f"(session {session_id})",
            )

        except Exception as error:

            print(
                "⚠️ Reminder WebSocket delivery failed:",
                error,
            )

    else:

        print(
            "⏰ Reminder due (no active session):",
            reminder["text"],
            f"(session {session_id})",
        )


async def reminder_scheduler_loop() -> None:

    while True:

        try:

            due_reminders = get_due_reminders()

            for reminder in due_reminders:

                updated = mark_reminder_triggered(
                    reminder["id"],
                )

                if updated is None:
                    continue

                await _deliver_reminder(updated)

        except Exception as error:

            print(
                "❌ Reminder scheduler error:",
                error,
            )

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def start_reminder_scheduler() -> asyncio.Task:

    return asyncio.create_task(
        reminder_scheduler_loop()
    )
