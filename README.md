# Weather MCP (Open-Meteo)

This project provides an MCP (Microservice Control Protocol) `weather` server that uses the Open-Meteo API via the `openmeteo-requests` Python client for forecasts.

## Changes
- Replaced National Weather Service (NWS) usage with Open-Meteo (`https://api.open-meteo.com`).
- `get_forecast(latitude, longitude)` now returns current weather and a short daily summary (next 3 days) based on Open-Meteo.
- `get_alerts(state)` now returns a message explaining that Open-Meteo does not provide state-level alerts and suggests alternatives.

## Usage examples
- Forecast by coordinates (Munich): `get_forecast(48.1351, 11.5820)`
- Forecast for central Michigan: `get_forecast(44.3148, -85.6024)`


