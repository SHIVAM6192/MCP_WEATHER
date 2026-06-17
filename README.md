# 🌤️ Weather & Air Quality MCP Server

A production-ready MCP server that gives Claude real-time weather,
air quality, forecasts, and health advisories for any city worldwide.

**No paid API keys needed** — uses Open-Meteo (100% free, no account required).

---

## 🗺️ Architecture

```
You (ask Claude)
     ↓
Claude Desktop / Claude Code
     ↓  (MCP protocol over stdio)
server.py  ← THIS FILE
     ↓  (HTTPS)
Open-Meteo API  (Free weather data)
Open-Meteo AQ API (Free air quality)
```

---

## ⚡ Quick Start

### 1. Get your Anthropic API Key
- Go to: https://console.anthropic.com
- Sign up → API Keys → Create Key
- Copy: `sk-ant-api03-...`

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-your-key-here"
```

### 2. Install dependencies
```bash
pip install mcp httpx anthropic
```

### 3. Test the tools directly
```bash
python test_client.py
```

### 4. Connect to Claude Desktop

Edit your Claude Desktop config:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "weather-advisory": {
      "command": "python",
      "args": ["/absolute/path/to/weather_mcp_server/server.py"],
      "env": {}
    }
  }
}
```

Restart Claude Desktop. You'll see a 🔨 tools icon appear.

---

## 🛠️ Available Tools

| Tool | Description |
|------|-------------|
| `get_current_weather` | Temperature, humidity, wind, precipitation |
| `get_air_quality` | AQI, PM2.5, PM10, CO, NO₂, O₃ |
| `get_5day_forecast` | 5-day daily forecast |
| `get_health_advisory` | Combined weather+AQ health advice by profile |

### Health profiles
- `general` — Standard advice
- `runner` — Outdoor exercise guidance  
- `elderly` — Heat/cold sensitivity
- `child` — Sun protection, safe conditions
- `respiratory` — Asthma/COPD considerations

---

## 💬 Example Prompts (in Claude Desktop)

```
"Is it safe to go for a run in Mumbai today?"

"What's the air quality like in Delhi right now?"

"Plan my outdoor wedding in Pune next 5 days — which day is best?"

"I have asthma. Should I go outside in Bangalore today?"

"Compare weather between London and Paris for my trip this week"
```

---

## 📁 File Structure

```
weather_mcp_server/
├── server.py                  ← Main MCP server (run this)
├── test_client.py             ← Test tools without Claude Desktop
├── requirements.txt           ← pip dependencies
├── claude_desktop_config.json ← Config template
└── README.md                  ← This file
```

---

## 🔧 Extending the Server

To add a new tool:

1. Add it to `list_tools()` with name, description, inputSchema
2. Add a handler `async def handle_my_tool(args)` 
3. Route it in `call_tool()` with `elif name == "my_tool"`

---

## 📡 APIs Used

| API | Cost | Docs |
|-----|------|------|
| Open-Meteo Weather | Free, no key | https://open-meteo.com |
| Open-Meteo Air Quality | Free, no key | https://open-meteo.com/en/docs/air-quality-api |
| Open-Meteo Geocoding | Free, no key | https://open-meteo.com/en/docs/geocoding-api |
