from openmeteo_sdk.Variable import Variable
from datetime import datetime, timezone

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


def _format_response(response) -> str:
    """Format a FlatBuffers response into the human-readable forecast string.
    This reuses the existing logic but operates on a single response object.
    """
    if response is None:
        return "Unable to fetch forecast data for this location."

    parts: list[str] = []

    # Current weather
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

    # Daily summary
    try:
        daily = response.Daily()
        if daily and daily.VariablesLength() > 0:
            tmax = []
            tmin = []
            precip = []

            for vi in range(daily.VariablesLength()):
                var = daily.Variables(vi)
                v = var.Variable()
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
