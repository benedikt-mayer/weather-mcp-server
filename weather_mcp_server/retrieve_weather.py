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
from .client import make_open_meteo_request
from .fetcher import _fetch_responses_with_retries
from .formatter import _format_response, _describe_weather_code

# Initialize FastMCP server (kept at module level for compatibility)
mcp = FastMCP("weather")

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
    parser.add_argument("--version", action="store_true", help="Print package version and exit")
    args = parser.parse_args(argv)

    if args.version:
        try:
            from importlib.metadata import version

            print(version("weather"))
        except Exception:
            print("version unknown")
        return

    # Initialize and run the server
    mcp.run(transport="stdio")