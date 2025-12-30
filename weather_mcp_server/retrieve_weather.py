from datetime import datetime, timezone

try:
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover - fallback for test environments without mcp

    class FastMCP:  # lightweight fallback used for tests and import-time safety
        def __init__(self, *_args, **_kwargs):
            pass

        def tool(self):
            def _dec(f):
                return f

            return _dec

        def run(self, *args, **kwargs):
            return None


import os

# Re-exported/adapted pieces from the refactored modules
from .fetcher import _fetch_responses_with_retries
from .formatter import _format_response, _describe_weather_code  # noqa: F401

# Initialize FastMCP server (kept at module level for compatibility)
# Allow environment variables to configure host/port/mount path at import time
_m_host = os.environ.get("WEATHER_HOST", "127.0.0.1")
_m_port = int(os.environ.get("WEATHER_PORT", "8000"))
_m_mount = os.environ.get("WEATHER_MOUNT_PATH", "/mcp")
mcp = FastMCP(
    "weather",
    host=_m_host,
    port=_m_port,
    mount_path=_m_mount,
    streamable_http_path=_m_mount,
)

# Constants
OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"


# `make_open_meteo_request` is provided by `weather_mcp_server.client` and
# re-exported at module level for backward compatibility.


# `_fetch_responses_with_retries` is implemented in `weather_mcp_server.fetcher`
# and re-exported at module level for backward compatibility.

# `_format_response` and `_describe_weather_code` are implemented in
# `weather_mcp_server.formatter` and re-exported at module level for
# backward compatibility.


@mcp.tool()
async def save_raw_forecast(latitude: float, longitude: float) -> str:
    """Fetch the raw formatted forecast and save it to the local `data/` directory.

    The saved file includes a small metadata header (attempts, whether hourly
    was present, generation time, model, timezone, etc.) followed by the
    formatted forecast text. Returns the file path on success or an error
    string starting with "Unable to fetch" on failure.
    """
    # Try to fetch responses with retries and collect metadata
    resp, meta = await _fetch_responses_with_retries(latitude, longitude)

    if resp is None:
        return "Unable to fetch forecast data for this location."

    text = _format_response(resp)

    os.makedirs("data", exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    lat_s = str(latitude).replace(".", "p").replace("-", "m")
    lon_s = str(longitude).replace(".", "p").replace("-", "m")
    fname = f"data/forecast_{lat_s}_{lon_s}_{ts}.txt"

    header_lines = [
        "Metadata:",
        f"Timestamp: {meta.get('timestamp')}",
        f"Attempts: {meta.get('attempts')}",
        f"Hourly present: {meta.get('hourly_present')}",
        f"Model: {meta.get('model')}",
        f"GenerationTimeMs: {meta.get('generation_ms')}",
        f"Timezone: {meta.get('timezone')}",
        f"UTC offset: {meta.get('utc_offset')}",
        f"Latitude: {meta.get('latitude')}",
        f"Longitude: {meta.get('longitude')}",
        f"Elevation: {meta.get('elevation')}",
        "---",
    ]

    with open(fname, "w", encoding="utf-8") as fh:
        fh.write("\n".join(header_lines) + "\n" + text)

    return fname


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location using Open-Meteo requests library.

    This function attempts up to 3 times (exponential backoff) to obtain a
    response that contains the Hourly block. If hourly is still missing after
    retries, the last response is formatted and returned; the caller (or
    `save_raw_forecast`) can examine stored metadata to see the attempts.
    """
    resp, meta = await _fetch_responses_with_retries(latitude, longitude)
    if resp is None:
        return "Unable to fetch forecast data for this location."

    return _format_response(resp)


def main(argv=None):
    """Entry point for running the weather MCP server.

    Accepts an optional argv list (for console scripts or tests). Supported options:
      --version    Print package version and exit
      run (default) Start the MCP server
    """
    import argparse

    parser = argparse.ArgumentParser(prog="weather")
    parser.add_argument("command", nargs="?", choices=["run"], default="run")
    parser.add_argument(
        "--version", action="store_true", help="Print package version and exit"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default=os.environ.get("WEATHER_TRANSPORT", "streamable-http"),
        help="Transport to use (default: streamable-http)",
    )
    parser.add_argument(
        "--mount-path",
        default=os.environ.get("WEATHER_MOUNT_PATH", "/mcp"),
        help="Mount path for HTTP transports (default: /mcp)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("WEATHER_HOST", "127.0.0.1"),
        help="Host to bind the HTTP server to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("WEATHER_PORT", "8000")),
        help="Port to bind the HTTP server to",
    )
    parser.add_argument(
        "--use-fake",
        action="store_true",
        help="Use fake Open-Meteo responses (for testing)",
    )
    args = parser.parse_args(argv)

    if args.version:
        try:
            from importlib.metadata import version

            print(version("weather"))
        except Exception:
            print("version unknown")
        return

    # If running an HTTP-like transport, prefer the streamable HTTP server by default
    if args.command == "run":
        transport = args.transport

        # Optionally inject fake Open-Meteo responses for integration testing
        if args.use_fake:

            class _FakeVar:
                def __init__(self, variable, value=None, values=None, agg=None):
                    self._variable = variable
                    self._value = value
                    self._values = values or []
                    self._agg = agg

                def Variable(self):
                    return self._variable

                def Value(self):
                    return self._value

                def ValuesAsNumpy(self):
                    return self._values

                def ValuesLength(self):
                    return len(self._values)

                def Values(self, i):
                    return self._values[i]

                def Aggregation(self):
                    return self._agg

            class _FakeBlock:
                def __init__(self, vars, time=0, interval=3600):
                    self._vars = vars
                    self._time = time
                    self._interval = interval

                def VariablesLength(self):
                    return len(self._vars)

                def Variables(self, i):
                    return self._vars[i]

                def Time(self):
                    return self._time

                def Interval(self):
                    return self._interval

            class _FakeResponse:
                def __init__(self, current, daily, hourly, utc_offset=0):
                    self._current = current
                    self._daily = daily
                    self._hourly = hourly
                    self._utc = utc_offset

                def Current(self):
                    return self._current

                def Daily(self):
                    return self._daily

                def Hourly(self):
                    return self._hourly

                def UtcOffsetSeconds(self):
                    return self._utc

            # Build a minimal plausible response
            async def _fake_make(lat, lon, params=None):
                cur = _FakeBlock(
                    [
                        _FakeVar(0, value=5.0),  # temperature
                        _FakeVar(1, value=1),  # weather_code
                    ]
                )
                daily = _FakeBlock(
                    [
                        _FakeVar(0, values=[6.0], agg=2),
                    ],
                    time=1609459200,
                    interval=86400,
                )
                hourly = _FakeBlock(
                    [
                        _FakeVar(0, values=[1.0] * 24),
                    ],
                    time=1609459200,
                    interval=3600,
                )
                return [_FakeResponse(cur, daily, hourly, utc_offset=0)]

        # Start the server with the requested transport
        # (host/port should be configured via FASTMCP_* env vars when needed)
        mcp.run(transport=transport, mount_path=args.mount_path)
