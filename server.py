"""
Weather & Air Quality MCP Server
Real-world problem: Helps users get weather + air quality data
and provides health/travel advisories using Claude as the brain.

Uses FREE APIs - No API keys required for weather/air quality!
Only needs: pip install mcp httpx
"""

import asyncio
import sys
import httpx
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ── Initialize MCP Server ──────────────────────────────────────────────────
app = Server("weather-advisory-server")


# ══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS  (Claude sees these as available tools)
# ══════════════════════════════════════════════════════════════════════════════

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """Register all tools Claude can call."""
    return [
        types.Tool(
            name="get_current_weather",
            description=(
                "Fetch real-time weather for any city. Returns temperature, "
                "humidity, wind speed, precipitation, and weather condition."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name (e.g. 'Mumbai', 'London', 'New York')"
                    },
                    "country_code": {
                        "type": "string",
                        "description": "ISO 2-letter country code (e.g. 'IN', 'US', 'GB'). Optional but improves accuracy."
                    }
                },
                "required": ["city"]
            }
        ),

        types.Tool(
            name="get_air_quality",
            description=(
                "Fetch current air quality index (AQI) and pollutant levels "
                "(PM2.5, PM10, CO, NO2, O3) for a city."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name"
                    },
                    "country_code": {
                        "type": "string",
                        "description": "ISO 2-letter country code. Optional."
                    }
                },
                "required": ["city"]
            }
        ),

        types.Tool(
            name="get_5day_forecast",
            description=(
                "Get a 5-day weather forecast for any city. "
                "Useful for travel planning and event scheduling."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name"
                    },
                    "country_code": {
                        "type": "string",
                        "description": "ISO 2-letter country code. Optional."
                    }
                },
                "required": ["city"]
            }
        ),

        types.Tool(
            name="get_health_advisory",
            description=(
                "Generate a health and outdoor activity advisory based on "
                "current weather + air quality. Great for runners, elderly, "
                "children, and people with respiratory conditions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name"
                    },
                    "country_code": {
                        "type": "string",
                        "description": "ISO 2-letter country code. Optional."
                    },
                    "profile": {
                        "type": "string",
                        "enum": ["general", "runner", "elderly", "child", "respiratory"],
                        "description": "User health profile for tailored advice"
                    }
                },
                "required": ["city", "profile"]
            }
        ),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

async def geocode_city(city: str, country_code: str = "") -> dict:
    """Convert city name → lat/lon using Open-Meteo geocoding (FREE)."""
    query = f"{city},{country_code}" if country_code else city
    url = "https://geocoding-api.open-meteo.com/v1/search"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params={"name": query, "count": 1, "language": "en", "format": "json"})
        resp.raise_for_status()
        data = resp.json()

    if not data.get("results"):
        raise ValueError(f"City '{city}' not found. Try adding a country code.")

    result = data["results"][0]
    return {
        "name": result["name"],
        "country": result.get("country", ""),
        "lat": result["latitude"],
        "lon": result["longitude"],
        "timezone": result.get("timezone", "UTC")
    }


WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Heavy thunderstorm with hail"
}

AQI_LEVELS = [
    (0,  50,  "Good",       "🟢", "Air quality is satisfactory."),
    (51, 100, "Moderate",   "🟡", "Acceptable; some pollutants may affect sensitive people."),
    (101,150, "Unhealthy (Sensitive)", "🟠", "Sensitive groups may experience health effects."),
    (151,200, "Unhealthy",  "🔴", "Everyone may begin to experience health effects."),
    (201,300, "Very Unhealthy","🟣","Health alert: everyone may experience serious effects."),
    (301,500, "Hazardous",  "⚫", "Health warning: emergency conditions.")
]

def aqi_category(aqi: float) -> tuple:
    for lo, hi, label, emoji, desc in AQI_LEVELS:
        if lo <= aqi <= hi:
            return label, emoji, desc
    return "Hazardous", "⚫", "Extreme pollution levels."

def pm25_to_aqi(pm25: float) -> int:
    """Convert PM2.5 µg/m³ → US AQI (simplified EPA formula)."""
    breakpoints = [
        (0.0, 12.0, 0, 50), (12.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150), (55.5, 150.4, 151, 200),
        (150.5, 250.4, 201, 300), (250.5, 500.4, 301, 500)
    ]
    for bp_lo, bp_hi, i_lo, i_hi in breakpoints:
        if bp_lo <= pm25 <= bp_hi:
            return round(((i_hi - i_lo) / (bp_hi - bp_lo)) * (pm25 - bp_lo) + i_lo)
    return 500


# ══════════════════════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════════

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Route tool calls to the correct handler."""

    if name == "get_current_weather":
        return await handle_current_weather(arguments)
    elif name == "get_air_quality":
        return await handle_air_quality(arguments)
    elif name == "get_5day_forecast":
        return await handle_forecast(arguments)
    elif name == "get_health_advisory":
        return await handle_health_advisory(arguments)
    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ── Tool 1: Current Weather ────────────────────────────────────────────────
async def handle_current_weather(args: dict) -> list[types.TextContent]:
    try:
        geo = await geocode_city(args["city"], args.get("country_code", ""))
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": geo["lat"], "longitude": geo["lon"],
            "current": [
                "temperature_2m", "relative_humidity_2m", "apparent_temperature",
                "precipitation", "weather_code", "wind_speed_10m",
                "wind_direction_10m", "surface_pressure", "visibility"
            ],
            "timezone": geo["timezone"]
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        c = data["current"]
        code = c.get("weather_code", 0)
        condition = WMO_CODES.get(code, f"Code {code}")

        result = {
            "location": f"{geo['name']}, {geo['country']}",
            "coordinates": {"lat": geo["lat"], "lon": geo["lon"]},
            "temperature_c": c["temperature_2m"],
            "feels_like_c": c["apparent_temperature"],
            "humidity_pct": c["relative_humidity_2m"],
            "precipitation_mm": c["precipitation"],
            "wind_speed_kmh": c["wind_speed_10m"],
            "wind_direction_deg": c["wind_direction_10m"],
            "condition": condition,
            "pressure_hpa": c["surface_pressure"],
        }
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error fetching weather: {e}")]


# ── Tool 2: Air Quality ────────────────────────────────────────────────────
async def handle_air_quality(args: dict) -> list[types.TextContent]:
    try:
        geo = await geocode_city(args["city"], args.get("country_code", ""))
        url = "https://air-quality-api.open-meteo.com/v1/air-quality"
        params = {
            "latitude": geo["lat"], "longitude": geo["lon"],
            "current": ["pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide", "ozone"],
            "timezone": geo["timezone"]
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        c = data["current"]
        pm25 = c.get("pm2_5", 0) or 0
        aqi = pm25_to_aqi(pm25)
        label, emoji, desc = aqi_category(aqi)

        result = {
            "location": f"{geo['name']}, {geo['country']}",
            "aqi": aqi,
            "aqi_category": label,
            "aqi_emoji": emoji,
            "aqi_description": desc,
            "pollutants": {
                "pm2_5_ugm3": round(pm25, 1),
                "pm10_ugm3": round(c.get("pm10", 0) or 0, 1),
                "carbon_monoxide_ugm3": round(c.get("carbon_monoxide", 0) or 0, 1),
                "nitrogen_dioxide_ugm3": round(c.get("nitrogen_dioxide", 0) or 0, 1),
                "ozone_ugm3": round(c.get("ozone", 0) or 0, 1),
            }
        }
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error fetching air quality: {e}")]


# ── Tool 3: 5-Day Forecast ─────────────────────────────────────────────────
async def handle_forecast(args: dict) -> list[types.TextContent]:
    try:
        geo = await geocode_city(args["city"], args.get("country_code", ""))
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": geo["lat"], "longitude": geo["lon"],
            "daily": [
                "weather_code", "temperature_2m_max", "temperature_2m_min",
                "precipitation_sum", "wind_speed_10m_max", "uv_index_max"
            ],
            "timezone": geo["timezone"],
            "forecast_days": 5
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        daily = data["daily"]
        forecast = []
        for i in range(5):
            code = daily["weather_code"][i]
            forecast.append({
                "date": daily["time"][i],
                "condition": WMO_CODES.get(code, f"Code {code}"),
                "temp_max_c": daily["temperature_2m_max"][i],
                "temp_min_c": daily["temperature_2m_min"][i],
                "precipitation_mm": daily["precipitation_sum"][i],
                "max_wind_kmh": daily["wind_speed_10m_max"][i],
                "uv_index": daily["uv_index_max"][i],
            })

        result = {"location": f"{geo['name']}, {geo['country']}", "forecast": forecast}
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error fetching forecast: {e}")]


# ── Tool 4: Health Advisory ────────────────────────────────────────────────
async def handle_health_advisory(args: dict) -> list[types.TextContent]:
    """Combines weather + AQI to generate a structured health advisory."""
    try:
        city = args["city"]
        country_code = args.get("country_code", "")
        profile = args.get("profile", "general")

        # Fetch both in parallel
        weather_result, aq_result = await asyncio.gather(
            handle_current_weather({"city": city, "country_code": country_code}),
            handle_air_quality({"city": city, "country_code": country_code})
        )

        weather = json.loads(weather_result[0].text)
        aq = json.loads(aq_result[0].text)

        # Build advisory logic
        warnings = []
        tips = []
        outdoor_safe = True

        # AQI checks
        aqi = aq["aqi"]
        if aqi > 300:
            outdoor_safe = False
            warnings.append("🚨 HAZARDOUS air quality. Stay indoors.")
        elif aqi > 200:
            outdoor_safe = False
            warnings.append("⚠️ Very unhealthy air. Avoid all outdoor activity.")
        elif aqi > 150:
            warnings.append("⚠️ Unhealthy air. Sensitive groups should stay indoors.")
            if profile in ["elderly", "child", "respiratory"]:
                outdoor_safe = False

        # Weather checks
        temp = weather["temperature_c"]
        feels_like = weather["feels_like_c"]
        wind = weather["wind_speed_kmh"]
        precip = weather["precipitation_mm"]

        if feels_like > 40:
            warnings.append(f"🌡️ Extreme heat ({feels_like}°C feels like). Risk of heat stroke.")
            tips.append("Drink water every 20 mins. Avoid direct sun 11am–4pm.")
            if profile == "runner":
                outdoor_safe = False
        elif feels_like > 35:
            warnings.append(f"☀️ High heat ({feels_like}°C feels like). Stay hydrated.")
            tips.append("Exercise early morning or after sunset.")

        if feels_like < 0:
            warnings.append(f"🥶 Freezing conditions ({feels_like}°C feels like).")
            tips.append("Layer up. Risk of frostbite with prolonged exposure.")

        if precip > 5:
            warnings.append(f"🌧️ Heavy rain ({precip}mm). Flooding possible.")
            tips.append("Carry waterproof gear. Avoid low-lying areas.")
        elif precip > 0:
            tips.append("🌂 Light rain expected. Carry an umbrella.")

        if wind > 60:
            warnings.append(f"💨 Strong winds ({wind} km/h). Outdoor sports unsafe.")
            if profile == "runner":
                outdoor_safe = False
        elif wind > 30:
            tips.append(f"🌬️ Moderate winds ({wind} km/h). Secure loose items.")

        # UV check from current weather code
        if weather.get("condition") in ["Clear sky", "Mainly clear"]:
            tips.append("🕶️ High UV likely on clear days. Wear SPF 30+.")

        # Profile-specific advice
        profile_tips = {
            "runner": "Best time to run: 5–7 AM or after 7 PM.",
            "elderly": "Avoid prolonged outdoor exposure. Keep emergency contacts handy.",
            "child": "Ensure children wear hats and apply sunscreen.",
            "respiratory": "Keep inhaler accessible. Check AQI before any outdoor activity.",
            "general": "Stay informed about changing conditions."
        }
        tips.append(profile_tips.get(profile, profile_tips["general"]))

        advisory = {
            "location": weather["location"],
            "profile": profile,
            "outdoor_activity_safe": outdoor_safe,
            "overall_rating": "Good ✅" if (outdoor_safe and aqi < 100 and not warnings) else
                              "Caution ⚠️" if warnings else "Unsafe ❌",
            "current_conditions": {
                "temperature_c": temp,
                "feels_like_c": feels_like,
                "condition": weather["condition"],
                "aqi": aqi,
                "aqi_category": aq["aqi_category"]
            },
            "warnings": warnings,
            "tips": tips
        }
        return [types.TextContent(type="text", text=json.dumps(advisory, indent=2))]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error generating advisory: {e}")]


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    print("Weather Advisory MCP Server starting...", file=sys.stderr)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
