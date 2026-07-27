from __future__ import annotations

from typing import Any

import httpx

from app.tools.base import BaseTool

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO Weather interpretation codes → short labels
# https://open-meteo.com/en/docs
_WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# Offline / API-failure fallback (keeps chat usable without network).
_MOCK_WEATHER: dict[str, dict[str, Any]] = {
    "london": {"city": "London", "temp_c": 14, "condition": "Cloudy", "humidity": 72, "wind_kph": 18},
    "new york": {"city": "New York", "temp_c": 22, "condition": "Sunny", "humidity": 48, "wind_kph": 12},
    "tokyo": {"city": "Tokyo", "temp_c": 27, "condition": "Humid", "humidity": 80, "wind_kph": 10},
    "chennai": {"city": "Chennai", "temp_c": 33, "condition": "Hot and humid", "humidity": 78, "wind_kph": 15},
    "san francisco": {
        "city": "San Francisco",
        "temp_c": 16,
        "condition": "Foggy",
        "humidity": 85,
        "wind_kph": 20,
    },
}


class WeatherTool(BaseTool):
    """Current weather via Open-Meteo (geocode city → lat/lon → forecast)."""

    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return (
            "Get the current weather for a city using live Open-Meteo data. "
            "Use when the user asks about temperature, conditions, or weather for a place. "
            "Returns temperature in Celsius, condition, humidity, and wind."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. London, Tokyo, Chennai.",
                }
            },
            "required": ["city"],
            "additionalProperties": False,
        }

    def execute(self, **kwargs: Any) -> str:
        city = str(kwargs.get("city", "")).strip()
        if not city:
            raise ValueError("city is required")

        try:
            return self._fetch_open_meteo(city)
        except Exception as exc:  # noqa: BLE001 — fall back so chat still works offline
            mock = self._mock_fallback(city)
            return (
                f"{mock} "
                f"[fallback: mock — Open-Meteo unavailable: {type(exc).__name__}: {exc}]"
            )

    def _fetch_open_meteo(self, city: str) -> str:
        with httpx.Client(timeout=12.0) as client:
            place = self._geocode(client, city)
            current = self._current_weather(
                client,
                latitude=place["latitude"],
                longitude=place["longitude"],
            )

        code = int(current.get("weather_code", -1))
        condition = _WMO_CODES.get(code, f"Weather code {code}")
        temp = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        wind = current.get("wind_speed_10m")
        country = place.get("country") or ""
        admin = place.get("admin1") or ""
        label = place["name"]
        if admin:
            label = f"{label}, {admin}"
        if country:
            label = f"{label}, {country}"

        return (
            f"Weather for {label}: {temp}°C, {condition}, "
            f"humidity {humidity}%, wind {wind} km/h "
            f"[source: Open-Meteo]"
        )

    def _geocode(self, client: httpx.Client, city: str) -> dict[str, Any]:
        response = client.get(
            GEOCODE_URL,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") or []
        if not results:
            raise ValueError(f"Could not find city '{city}'")
        hit = results[0]
        return {
            "name": hit.get("name") or city,
            "latitude": hit["latitude"],
            "longitude": hit["longitude"],
            "country": hit.get("country"),
            "admin1": hit.get("admin1"),
        }

    def _current_weather(
        self,
        client: httpx.Client,
        *,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:
        response = client.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            },
        )
        response.raise_for_status()
        payload = response.json()
        current = payload.get("current")
        if not isinstance(current, dict):
            raise ValueError("Open-Meteo response missing current weather")
        return current

    def _mock_fallback(self, city: str) -> str:
        key = city.lower()
        data = _MOCK_WEATHER.get(key) or {
            "city": city.title(),
            "temp_c": 21,
            "condition": "Partly cloudy (mock)",
            "humidity": 55,
            "wind_kph": 11,
        }
        return (
            f"Weather for {data['city']}: {data['temp_c']}°C, {data['condition']}, "
            f"humidity {data['humidity']}%, wind {data['wind_kph']} kph"
        )
