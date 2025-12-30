# Agents & Tools — weather MCP

This document describes the agents/tools provided by this repository, how to run them, and how to diagnose intermittent issues (e.g., missing hourly blocks).

## Overview ✅
- The project exposes an MCP server `weather` (FastMCP) with tools to fetch and save forecasts using the Open‑Meteo client.
- Key tools (MCP methods):
  - `get_forecast(latitude, longitude)` → human-readable summary (Now, Daily, Hourly when available)
  - `save_raw_forecast(latitude, longitude)` → saves a timestamped raw file in `data/` with a diagnostic header

## Tooling
- Always use uv instead of pip

## Running the MCP server 🛠️
- Run locally (starts an HTTP-backed MCP server by default):

  ```bash
  # runs an HTTP server exposing the MCP endpoints at http://127.0.0.1:8000/mcp
  python -m weather

  # you can customize transport and binding options:
  python -m weather --transport streamable-http --host 0.0.0.0 --port 8000 --mount-path /mcp
  # or run using uv (recommended for production):
  uv run --with mcp python -m weather
  ```

- You can also set the following environment variables to configure defaults: `WEATHER_TRANSPORT`, `WEATHER_HOST`, `WEATHER_PORT`, `WEATHER_MOUNT_PATH`.

- Call tools programmatically by creating an MCP client and calling the tools above, or use the included utilities in the codebase.

## File format: saved raw forecasts (diagnostics) 📝
- `save_raw_forecast` writes files to `data/` with a filename like `forecast_{lat}_{lon}_{YYYYMMDD_HHMMSS}.txt`.
- Each file begins with a small metadata header that includes:
  - `Timestamp` (UTC, timezone-aware)
  - `Attempts` (how many requests were made, <= 3 by default)
  - `Hourly present` (True/False)
  - `Model`, `GenerationTimeMs`, `Timezone`, `UTC offset`, `Latitude`, `Longitude`, `Elevation`
- The metadata is followed by the human-readable forecast text (Now / Daily / Hourly or a "Hourly not available" note).

## Behavior: hourly block & retries 🔁
- The Open‑Meteo API does not always guarantee the Hourly block in every response.
- `get_forecast` and `save_raw_forecast` now implement a safe retry strategy:
  - Up to 3 attempts with exponential backoff (1s → 2s)
  - If hourly appears on a retry, that response is used and the metadata records the attempts and `Hourly present: True`.
  - If hourly is still missing after retries, the last response is returned and metadata records that hourly was absent.

## Testing & Linting 🧪/🔍
- Tests: `pytest` with `pytest-asyncio` is used. Tests live in `tests/test_weather.py`.
- Linting: `ruff` is used. CI runs `ruff format --check .` and `ruff check .`.
- **After every code change, run:** `ruff check --fix .` and `ruff format .` to ensure code quality and consistency.
- CI: GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push/pull_request, uses `uv` to sync dependencies from `uv.lock`, runs ruff checks and pytest.

## Debugging tips 🐞
- If hourly is missing repeatedly:
  - Inspect the saved raw file header in `data/` for `Attempts` and `GenerationTimeMs`.
  - Manually call the Open‑Meteo request using `make_open_meteo_request(lat, lon)` in a REPL to inspect `response.Hourly()` and other response metadata (Model, Timezone, UtcOffsetSeconds).
  - Check CI or service logs for rate limits or transient network errors.

## Extending the project ⚡
- To add new MCP tools, register them with `mcp.tool()` and include unit tests that use lightweight Fake FlatBuffers objects (see `tests/test_weather.py`).
- Consider adding more telemetry (request IDs, response headers) if you need long-term analytics.

## Contacts & Contributions
- Repo: `github.com/benedikt-mayer/weather-mcp-server`
- If useful, add a `CONTRIBUTING.md` that details local dev setup and how to write tests and add CI entries.

---

Concise, practical, and targeted at contributors who will call the agents, debug issues, or extend the server.