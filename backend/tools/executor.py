import json
from typing import Any, Awaitable, Callable, Optional

from backend.tools.reminders import (
    tool_cancel_reminder,
    tool_create_reminder,
    tool_get_reminders,
)
from backend.tools.weather import get_weather


ToolEventCallback = Optional[
    Callable[[dict[str, Any]], Awaitable[None]]
]

TOOL_LABELS = {
    "get_weather": "weather",
    "create_reminder": "create_reminder",
    "get_reminders": "get_reminders",
    "cancel_reminder": "cancel_reminder",
}


async def _emit_tool_event(
    callback: ToolEventCallback,
    event: dict[str, Any],
) -> None:

    if callback is None:
        return

    await callback(event)


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    user_id: str = "default",
    on_event: ToolEventCallback = None,
) -> dict[str, Any]:

    tool_label = TOOL_LABELS.get(
        tool_name,
        tool_name,
    )

    await _emit_tool_event(
        on_event,
        {
            "type": "tool",
            "tool": tool_label,
            "status": "started",
        },
    )

    try:

        if tool_name == "get_weather":

            result = get_weather(
                location=arguments.get("location", ""),
                query_type=arguments.get(
                    "query_type",
                    "current",
                ),
            )

        elif tool_name == "create_reminder":

            result = tool_create_reminder(
                text=arguments.get("text", ""),
                remind_at=arguments.get("remind_at", ""),
                user_id=user_id,
            )

        elif tool_name == "get_reminders":

            result = tool_get_reminders(
                user_id=user_id,
                pending_only=arguments.get(
                    "pending_only",
                    True,
                ),
            )

        elif tool_name == "cancel_reminder":

            result = tool_cancel_reminder(
                user_id=user_id,
                reminder_id=arguments.get("reminder_id"),
                text_match=arguments.get("text_match"),
            )

        else:

            result = {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
            }

        if not result.get("success", True):

            await _emit_tool_event(
                on_event,
                {
                    "type": "tool_error",
                    "tool": tool_label,
                    "text": result.get(
                        "error",
                        "Tool execution failed.",
                    ),
                },
            )

        else:

            status = (
                "saved"
                if tool_name == "create_reminder"
                else "completed"
            )

            await _emit_tool_event(
                on_event,
                {
                    "type": "tool",
                    "tool": tool_label,
                    "status": status,
                },
            )

        return result

    except Exception as error:

        await _emit_tool_event(
            on_event,
            {
                "type": "tool_error",
                "tool": tool_label,
                "text": str(error),
            },
        )

        return {
            "success": False,
            "error": str(error),
        }


def serialize_tool_result(
    result: dict[str, Any],
) -> str:

    return json.dumps(result, default=str)
