# Compatibility alias module used by some tests and external callers.
# Expose the lightweight functions directly so code that references
# `weather_mcp_server.weather.make_open_meteo_request` keeps working.
from .retrieve_weather import (
    make_open_meteo_request,
    get_forecast,
    save_raw_forecast,
    _describe_weather_code,
)

__all__ = [
    "make_open_meteo_request",
    "get_forecast",
    "save_raw_forecast",
    "_describe_weather_code",
]
