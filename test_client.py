import anthropic
import asyncio
import json
import os
import httpx


# ── Direct API calls (no MCP needed for quick testing) ────────────────────

BASE_GEO = "https://geocoding-api.open-meteo.com/v1/search"
BASE_WEATHER = "https://api.open-meteo.com/v1/forecast"
BASE_AQ = "https://air-quality-api.open-meteo.com/v1/air-quality"

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 51: "Light drizzle", 61: "Slight rain", 63: "Moderate rain",
    65: "Heavy rain", 71: "Slight snow", 80: "Slight showers",
    95: "Thunderstorm"
}

async def geocode(city: str):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(BASE_GEO, params={"name": city, "count": 1, "format": "json"})
        data = r.json()
    if not data.get("results"):
        raise ValueError(f"City not found: {city}")
    g = data["results"][0]
    return g["name"], g.get("country",""), g["latitude"], g["longitude"], g.get("timezone","UTC")

async def test_weather(city="Pune"):
    print(f"\n{'='*50}")
    print(f"🌤️  TEST: Current Weather for {city}")
    print('='*50)
    name, country, lat, lon, tz = await geocode(city)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(BASE_WEATHER, params={
            "latitude": lat, "longitude": lon,
            "current": ["temperature_2m","apparent_temperature","relative_humidity_2m",
                        "precipitation","weather_code","wind_speed_10m"],
            "timezone": tz
        })
        data = r.json()
    c = data["current"]
    print(f"📍 {name}, {country}")
    print(f"🌡️  Temperature : {c['temperature_2m']}°C (feels {c['apparent_temperature']}°C)")
    print(f"💧  Humidity    : {c['relative_humidity_2m']}%")
    print(f"🌬️  Wind        : {c['wind_speed_10m']} km/h")
    print(f"🌧️  Precip      : {c['precipitation']} mm")
    print(f"☁️  Condition   : {WMO_CODES.get(c['weather_code'], 'Unknown')}")

async def test_air_quality(city="Pune"):
    print(f"\n{'='*50}")
    print(f"🏭  TEST: Air Quality for {city}")
    print('='*50)
    name, country, lat, lon, tz = await geocode(city)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(BASE_AQ, params={
            "latitude": lat, "longitude": lon,
            "current": ["pm10","pm2_5","carbon_monoxide","nitrogen_dioxide","ozone"],
            "timezone": tz
        })
        data = r.json()
    c = data["current"]
    pm25 = c.get("pm2_5", 0) or 0
    print(f"📍 {name}, {country}")
    print(f"🟡  PM2.5   : {pm25:.1f} µg/m³")
    print(f"🟠  PM10    : {c.get('pm10',0):.1f} µg/m³")
    print(f"💨  CO      : {c.get('carbon_monoxide',0):.1f} µg/m³")
    print(f"🔵  NO₂     : {c.get('nitrogen_dioxide',0):.1f} µg/m³")
    print(f"☁️  O₃      : {c.get('ozone',0):.1f} µg/m³")

async def test_forecast(city="Mumbai"):
    print(f"\n{'='*50}")
    print(f"📅  TEST: 5-Day Forecast for {city}")
    print('='*50)
    name, country, lat, lon, tz = await geocode(city)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(BASE_WEATHER, params={
            "latitude": lat, "longitude": lon,
            "daily": ["weather_code","temperature_2m_max","temperature_2m_min",
                      "precipitation_sum","uv_index_max"],
            "timezone": tz, "forecast_days": 5
        })
        data = r.json()
    daily = data["daily"]
    print(f"📍 {name}, {country}\n")
    for i in range(5):
        code = daily["weather_code"][i]
        print(f"  {daily['time'][i]}  |  {WMO_CODES.get(code,'?'):20s}  |  "
              f"{daily['temperature_2m_min'][i]}°C – {daily['temperature_2m_max'][i]}°C  |  "
              f"UV:{daily['uv_index_max'][i]}")


async def test_claude_with_mcp():
    """
    Uses Anthropic API to ask Claude a question.
    Claude will conceptually use the MCP tools (when server is running).
    This test shows the API integration pattern.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n⚠️  ANTHROPIC_API_KEY not set. Skipping Claude API test.")
        print("   Set it with: export ANTHROPIC_API_KEY=sk-ant-...")
        return

    print(f"\n{'='*50}")
    print("🤖  TEST: Claude API Integration")
    print('='*50)

    
    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": (
                "I'm a runner planning to exercise in Pune, India today. "
                "Is it safe to run outside? What should I know about the weather and air quality?"
            )
        }],
        system=(
            "You are a health and weather advisor. "
            "When connected to the weather-advisory MCP server, use the get_health_advisory tool "
            "with profile='runner' to fetch real data. "
            "For now, provide general guidance based on typical Pune conditions in March."
        )
    )

    print("Claude's Response:")
    print("-" * 40)
    print(message.content[0].text)


async def main():
    print("🚀 Weather MCP Server - Direct Tool Tests")
    print("   (These test the underlying APIs the MCP tools use)\n")

    await test_weather("Pune")
    await test_air_quality("Pune")
    await test_forecast("Mumbai")
    await test_claude_with_mcp()

    print(f"\n{'='*50}")
    print("✅  All tests complete!")
    print("📌  Next: Connect server.py to Claude Desktop")
    print('='*50)

if __name__ == "__main__":
    asyncio.run(main())
