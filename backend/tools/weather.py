import os
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)

_key_status_logged = False


def _log_weather_key_status() -> None:

    global _key_status_logged

    if _key_status_logged:
        return

    _key_status_logged = True

    detected = bool(_get_weather_api_key())

    print(
        "Weather API key detected:",
        "YES" if detected else "NO",
    )


def _get_weather_api_key() -> Optional[str]:

    for env_name in (
        "WEATHER_API_KEY",
        "OPENWEATHER_API_KEY",
        "WEATHERAPI_API_KEY",
        "OPENWEATHERMAP_API_KEY",
    ):

        value = os.getenv(env_name)

        if value:
            return value

    return None


def get_weather(
    location: str,
    query_type: str = "current",
) -> dict[str, Any]:

    _log_weather_key_status()

    api_key = _get_weather_api_key()

    if not api_key:

        return {
            "success": False,
            "error": "Weather API key is not configured on the server.",
        }

    location = (location or "").strip()

    if not location:

        return {
            "success": False,
            "error": "A location is required.",
        }

    query_type = (query_type or "current").lower()

    try:

        if query_type == "forecast":

            url = "https://api.weatherapi.com/v1/forecast.json"

            params = {
                "key": api_key,
                "q": location,
                "days": 2,
                "aqi": "no",
                "alerts": "no",
            }

        else:

            url = "https://api.weatherapi.com/v1/current.json"

            params = {
                "key": api_key,
                "q": location,
                "aqi": "no",
            }

        with httpx.Client(timeout=10.0) as client:

            response = client.get(
                url,
                params=params,
            )

        if response.status_code != 200:

            return {
                "success": False,
                "error": (
                    "Weather service returned an error for that location."
                ),
                "status_code": response.status_code,
            }

        payload = response.json()

        current = payload.get("current", {})
        location_info = payload.get("location", {})

        result = {
            "success": True,
            "location": location_info.get("name"),
            "region": location_info.get("region"),
            "country": location_info.get("country"),
            "temperature_c": current.get("temp_c"),
            "temperature_f": current.get("temp_f"),
            "condition": (
                current.get("condition", {}).get("text")
            ),
            "humidity": current.get("humidity"),
            "wind_kph": current.get("wind_kph"),
            "localtime": location_info.get("localtime"),
        }

        if query_type == "forecast":

            forecast_days = (
                payload.get("forecast", {})
                .get("forecastday", [])
            )

            result["forecast"] = [
                {
                    "date": day.get("date"),
                    "max_c": day.get("day", {}).get("maxtemp_c"),
                    "min_c": day.get("day", {}).get("mintemp_c"),
                    "condition": (
                        day.get("day", {})
                        .get("condition", {})
                        .get("text")
                    ),
                    "chance_of_rain": (
                        day.get("day", {})
                        .get("daily_chance_of_rain")
                    ),
                }
                for day in forecast_days
            ]

        return result

    except httpx.TimeoutException:

        return {
            "success": False,
            "error": "Weather request timed out.",
        }

    except Exception as error:

        return {
            "success": False,
            "error": f"Weather lookup failed: {error}",
        }
