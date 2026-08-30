import json
import os
from typing import Any, Awaitable, Callable, Optional

from dotenv import load_dotenv
from groq import APIStatusError, AsyncGroq

from backend.database import now_local
from backend.tools.executor import (
    execute_tool,
    serialize_tool_result,
)


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)

MAX_TOOL_ITERATIONS = 6

print(
    "Groq API key detected:",
    "YES" if GROQ_API_KEY else "NO",
)

_async_client: AsyncGroq | None = None

ToolEventCallback = Optional[
    Callable[[dict[str, Any]], Awaitable[None]]
]

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Get current weather or a short forecast for a city "
                "or location."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": (
                            "City or place name, e.g. Vizianagaram"
                        ),
                    },
                    "query_type": {
                        "type": "string",
                        "enum": ["current", "forecast"],
                        "description": (
                            "Use forecast for tomorrow/rain questions."
                        ),
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": (
                "Create a reminder for the user at a specific time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": (
                            "What to remind the user about"
                        ),
                    },
                    "remind_at": {
                        "type": "string",
                        "description": (
                            "Absolute reminder time in ISO 8601 using "
                            "timezone Asia/Kolkata"
                        ),
                    },
                },
                "required": ["text", "remind_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_reminders",
            "description": "List the user's reminders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pending_only": {
                        "type": "boolean",
                        "description": (
                            "If true, return only pending reminders"
                        ),
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_reminder",
            "description": "Cancel a pending reminder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {
                        "type": "integer",
                        "description": "Reminder id if known",
                    },
                    "text_match": {
                        "type": "string",
                        "description": (
                            "Partial text to match a pending reminder"
                        ),
                    },
                },
            },
        },
    },
]


def get_registered_tool_names() -> list[str]:

    return [
        tool["function"]["name"]
        for tool in TOOL_DEFINITIONS
    ]


def _get_async_client() -> AsyncGroq:

    global _async_client

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY not found in .env"
        )

    if _async_client is None:
        _async_client = AsyncGroq(
            api_key=GROQ_API_KEY
        )

    return _async_client


def _system_instruction() -> str:

    current_time = now_local().strftime(
        "%Y-%m-%d %H:%M:%S %Z"
    )

    return (
        "You are JARVIS, a helpful voice assistant. "
        "Answer naturally and concisely for spoken responses. "
        f"The current local time is {current_time} "
        "(timezone Asia/Kolkata). "
        "When the user asks about weather, call get_weather. "
        "When the user asks for a reminder, call create_reminder "
        "with remind_at as an absolute ISO 8601 datetime in "
        "Asia/Kolkata. Convert phrases like 'in 1 hour', "
        "'tomorrow at 9 AM', or 'today at 6 PM' into the correct "
        "absolute datetime before calling the tool. "
        "When the user asks to list reminders, call get_reminders. "
        "When the user asks to cancel a reminder, call cancel_reminder. "
        "For normal conversation, respond directly without tools. "
        "If a tool fails, apologize briefly and do not expose "
        "technical details."
    )


def _parse_tool_arguments(
    raw_arguments: str,
) -> dict[str, Any]:

    if not raw_arguments:
        return {}

    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {}

    if isinstance(parsed, dict):
        return parsed

    return {}


async def get_response_async(
    message: str,
    user_id: str = "default",
    on_event: ToolEventCallback = None,
) -> str:

    client = _get_async_client()

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": _system_instruction(),
        },
        {
            "role": "user",
            "content": message,
        },
    ]

    try:

        for _ in range(MAX_TOOL_ITERATIONS):

            response = (
                await client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                )
            )

            choice = response.choices[0]
            assistant_message = choice.message

            if not assistant_message.tool_calls:

                return (
                    assistant_message.content
                    or "Sorry, I couldn't generate a response."
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": (
                                    tool_call
                                    .function
                                    .name
                                ),
                                "arguments": (
                                    tool_call
                                    .function
                                    .arguments
                                ),
                            },
                        }
                        for tool_call in (
                            assistant_message.tool_calls
                        )
                    ],
                }
            )

            for tool_call in assistant_message.tool_calls:

                tool_name = tool_call.function.name
                tool_args = _parse_tool_arguments(
                    tool_call.function.arguments
                )

                tool_result = await execute_tool(
                    tool_name,
                    tool_args,
                    user_id=user_id,
                    on_event=on_event,
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": serialize_tool_result(
                            tool_result
                        ),
                    }
                )

        return (
            "Sorry, I couldn't complete that request."
        )

    except APIStatusError as error:

        raise RuntimeError(
            "Groq API request failed. Please try again."
        ) from error

    except Exception as error:

        if isinstance(error, RuntimeError):
            raise

        raise RuntimeError(
            "Groq request failed. Please try again."
        ) from error


def get_response(
    message: str,
    user_id: str = "default",
) -> str:

    import asyncio

    return asyncio.run(
        get_response_async(
            message,
            user_id=user_id,
        )
    )
