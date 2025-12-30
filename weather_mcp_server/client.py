try:
    import openmeteo_requests
except Exception:  # pragma: no cover - fallback for environments without the package

    class _FallbackAsyncClient:
        async def weather_api(self, url, params=None):
            raise RuntimeError("openmeteo_requests not available")

    class _FallbackModule:
        def AsyncClient(self):
            return _FallbackAsyncClient()

    openmeteo_requests = _FallbackModule()

# Base URL for Open-Meteo
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
