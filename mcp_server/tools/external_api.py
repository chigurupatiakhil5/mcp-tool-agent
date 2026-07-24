import httpx
from typing_extensions import TypedDict

from mcp_server.instance import mcp
from mcp_server.types import ToolError


class WeatherResult(TypedDict):
    city: str
    region: str | None
    country: str | None
    temperature_c: float
    windspeed_kmh: float
    conditions: str
    observed_at: str


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SECONDS = 10

# WMO weather codes, as used by Open-Meteo's current_weather.weathercode.
# https://open-meteo.com/en/docs - not every code exists here, only the
# common ones; anything unlisted falls back to the raw numeric code.
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


@mcp.tool()
async def get_current_weather(city: str) -> WeatherResult | ToolError:
    """Look up the current weather for a city.

    Calls Open-Meteo, a free weather API with no API key required. This is
    an async tool: it makes real network requests, so it awaits them instead
    of blocking the whole server while it waits for a response.

    Args:
        city: City name to look up, e.g. "Austin" or "Austin, TX".
    """
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        try:
            geo_response = await client.get(GEOCODING_URL, params={"name": city, "count": 1})
            geo_response.raise_for_status()
        except httpx.TimeoutException:
            return {"error": f"Geocoding request for '{city}' timed out"}
        except httpx.HTTPStatusError as exc:
            return {"error": f"Geocoding API returned {exc.response.status_code}"}

        geo_data = geo_response.json()
        results = geo_data.get("results")
        if not results:
            return {"error": f"No location found matching '{city}'"}

        location = results[0]
        latitude = location["latitude"]
        longitude = location["longitude"]

        try:
            weather_response = await client.get(
                FORECAST_URL,
                params={"latitude": latitude, "longitude": longitude, "current_weather": "true"},
            )
            weather_response.raise_for_status()
        except httpx.TimeoutException:
            return {"error": f"Weather request for '{city}' timed out"}
        except httpx.HTTPStatusError as exc:
            return {"error": f"Weather API returned {exc.response.status_code}"}

        current = weather_response.json()["current_weather"]
        weather_code = current["weathercode"]

        return {
            "city": location["name"],
            "region": location.get("admin1"),
            "country": location.get("country"),
            "temperature_c": current["temperature"],
            "windspeed_kmh": current["windspeed"],
            "conditions": WEATHER_CODES.get(weather_code, f"Unknown (code {weather_code})"),
            "observed_at": current["time"],
        }
