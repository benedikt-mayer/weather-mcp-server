import openmeteo_requests
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timezone
from openmeteo_sdk.Variable import Variable

# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"


async def make_open_meteo_request(
    latitude: float, longitude: float, params: dict | None = None
):
    """Make a request using the openmeteo-requests AsyncClient.

    Returns the list of responses (FlatBuffers-based wrappers) or None on error.
    """
    default_params = {
        "latitude": latitude,
        "longitude": longitude,
        # ask for current weather, daily summaries and hourly variables
        "current_weather": True,
        "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"],
        "hourly": ["temperature_2m", "precipitation", "wind_speed_10m"],
        "timezone": "auto",
    }

    if params:
        default_params.update(params)

    openmeteo = openmeteo_requests.AsyncClient()
    try:
        responses = await openmeteo.weather_api(OPEN_METEO_BASE, params=default_params)
        return responses
    except Exception:
        return None


# Mapping of Open-Meteo weather codes to human-readable descriptions
WEATHER_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Drizzle: Light",
    53: "Drizzle: Moderate",
    55: "Drizzle: Dense",
    61: "Rain: Slight",
    63: "Rain: Moderate",
    65: "Rain: Heavy",
    71: "Snow: Slight",
    73: "Snow: Moderate",
    75: "Snow: Heavy",
    77: "Snow grains",
    80: "Rain showers: Slight",
    81: "Rain showers: Moderate",
    82: "Rain showers: Violent",
    95: "Thunderstorm: Slight or moderate",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _describe_weather_code(code: int | None) -> str:
    if code is None:
        return "Unknown"
    return WEATHER_CODE_MAP.get(code, f"Code {code}")


import os


@mcp.tool()
async def save_raw_forecast(latitude: float, longitude: float) -> str:
    """Fetch the raw formatted forecast (exactly as returned by get_forecast)
    and save it to the local `data/` directory (ignored by git). Returns the file path.
    """
    # Reuse get_forecast to produce the same formatted text
    text = await get_forecast(latitude, longitude)
    if text.startswith("Unable to fetch"):
        return text

    os.makedirs("data", exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    # sanitize coordinates for filename
    lat_s = str(latitude).replace(".", "p").replace("-", "m")
    lon_s = str(longitude).replace(".", "p").replace("-", "m")
    fname = f"data/forecast_{lat_s}_{lon_s}_{ts}.txt"
    with open(fname, "w", encoding="utf-8") as fh:
        fh.write(text)
    return fname


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location using Open-Meteo requests library.

    Returns a brief, human-readable summary containing current weather and a
    short daily forecast (next 3 days). Uses the `openmeteo-requests` client
    to retrieve FlatBuffers responses efficiently.
    """
    responses = await make_open_meteo_request(latitude, longitude)
    if not responses:
        return "Unable to fetch forecast data for this location."

    # Process the first response (single location)
    response = responses[0]

    parts: list[str] = []

    # Current weather (try to read from the Current() block)
    try:
        current = response.Current()
        if current and current.VariablesLength() > 0:
            temp = None
            windspeed = None
            winddir = None
            code = None
            for i in range(current.VariablesLength()):
                var = current.Variables(i)
                v = var.Variable()
                if v == Variable.temperature:
                    temp = var.Value()
                elif v == Variable.wind_speed:
                    windspeed = var.Value()
                elif v == Variable.wind_direction:
                    winddir = var.Value()
                elif v == Variable.weather_code:
                    code = int(var.Value())

            parts.append(
                f"Now:\nTemperature: {temp}°C\n"
                + (
                    f"Wind: {windspeed} km/h at {winddir}°\n"
                    if windspeed is not None
                    else ""
                )
                + f"Conditions: {_describe_weather_code(code) if code is not None else 'Unknown'}"
            )
        else:
            parts.append("Current weather: not available.")
    except Exception:
        parts.append("Current weather: not available.")

    # Daily summary (next 3 days)
    try:
        daily = response.Daily()
        if daily and daily.VariablesLength() > 0:
            tmax = []
            tmin = []
            precip = []

            for vi in range(daily.VariablesLength()):
                var = daily.Variables(vi)
                v = var.Variable()
                # Temperature variables appear twice (max/min) and use Aggregation to distinguish
                agg = getattr(var, "Aggregation", lambda: None)()
                values = []
                try:
                    values = var.ValuesAsNumpy().tolist()
                except Exception:
                    try:
                        values = [var.Values(i) for i in range(var.ValuesLength())]
                    except Exception:
                        values = []

                if v == Variable.temperature:
                    if agg == 2:  # max
                        tmax = values
                    elif agg == 1:  # min
                        tmin = values
                elif v == Variable.precipitation:
                    precip = values

            # Build date strings from daily.Time(), Interval(), and UtcOffsetSeconds()
            dates_list = []
            start_ts = daily.Time()
            interval = daily.Interval()
            utc_offset = (
                response.UtcOffsetSeconds()
                if hasattr(response, "UtcOffsetSeconds")
                else 0
            )
            length = max(len(tmax), len(tmin), len(precip))
            for i in range(min(3, length)):
                ts = start_ts + i * interval + utc_offset
                date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
                    "%Y-%m-%d"
                )
                tm = tmax[i] if i < len(tmax) else "N/A"
                tn = tmin[i] if i < len(tmin) else "N/A"
                pr = precip[i] if i < len(precip) else "N/A"
                dates_list.append((date_str, tm, tn, pr))

            parts.append(
                "Daily Forecast:\n"
                + "\n".join(
                    [
                        f"{d}: High {tm}°C, Low {tn}°C, Precipitation: {pr} mm"
                        for d, tm, tn, pr in dates_list
                    ]
                )
            )
        else:
            parts.append("Daily forecast: not available.")
    except Exception:
        parts.append("Daily forecast: not available.")

    # Hourly summary (next 24 hours)
    try:
        hourly = response.Hourly()
        if hourly and hourly.VariablesLength() > 0:
            temps = []
            precs = []
            winds = []

            for vi in range(hourly.VariablesLength()):
                var = hourly.Variables(vi)
                v = var.Variable()
                try:
                    values = var.ValuesAsNumpy().tolist()
                except Exception:
                    try:
                        values = [var.Values(i) for i in range(var.ValuesLength())]
                    except Exception:
                        values = []

                if v == Variable.temperature:
                    temps = values
                elif v == Variable.precipitation:
                    precs = values
                elif v == Variable.wind_speed:
                    winds = values

            start = hourly.Time()
            interval = hourly.Interval()
            utc_offset = (
                response.UtcOffsetSeconds()
                if hasattr(response, "UtcOffsetSeconds")
                else 0
            )
            length = max(len(temps), len(precs), len(winds))
            hourly_lines: list[str] = []
            for i in range(min(24, length)):
                ts = start + i * interval + utc_offset
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
                    "%Y-%m-%d %H:%M"
                )
                t = temps[i] if i < len(temps) else "N/A"
                p = precs[i] if i < len(precs) else "N/A"
                w = winds[i] if i < len(winds) else "N/A"
                hourly_lines.append(f"{dt}: {t}°C, Precip: {p} mm, Wind: {w} km/h")

            parts.append("Hourly Forecast (next 24h):\n" + "\n".join(hourly_lines))
        else:
            parts.append("Hourly forecast: not available.")
    except Exception:
        parts.append("Hourly forecast: not available.")

    return "\n---\n".join(parts)


def main():
    # Initialize and run the server
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
