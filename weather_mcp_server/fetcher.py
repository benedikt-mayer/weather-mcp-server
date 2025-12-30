import asyncio
from datetime import datetime, timezone

from .client import make_open_meteo_request


async def _fetch_responses_with_retries(
    latitude: float,
    longitude: float,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
):
    """Call make_open_meteo_request repeatedly until the Hourly block is present
    or until attempts are exhausted. Returns (response_or_None, metadata_dict).
    """
    attempt = 0
    delay = initial_delay
    last_resp = None

    while attempt < max_attempts:
        attempt += 1
        # Allow tests (and callers) to monkeypatch the public `weather` alias
        # module's `make_open_meteo_request` (used in the old implementation).
        # Try to prefer that if present, otherwise fall back to the client.
        # Prefer a patched function on `retrieve_weather` (old module-local
        # behavior), then the compatibility `weather` alias, then the client.
        from .client import make_open_meteo_request as _default_make

        _make = None
        try:
            from . import retrieve_weather as _retrieve
            _rw = getattr(_retrieve, "make_open_meteo_request", None)
        except Exception:
            _rw = None

        # Prefer a patched retrieve_weather.make_open_meteo_request if it differs
        # from the default client implementation; otherwise prefer the `weather`
        # compatibility alias (which tests sometimes patch).
        if _rw is not None and _rw is not _default_make:
            _make = _rw
        else:
            try:
                from . import weather as _weather  # compatibility alias
                _make = getattr(_weather, "make_open_meteo_request", None)
            except Exception:
                _make = None

        if _make is None:
            _make = _default_make

        responses = await _make(latitude, longitude)
        if responses and len(responses) > 0:
            last_resp = responses[0]
            try:
                hourly = last_resp.Hourly()
                hourly_present = hourly is not None and hourly.VariablesLength() > 0
            except Exception:
                hourly_present = False
        else:
            hourly_present = False

        if hourly_present:
            break

        if attempt < max_attempts:
            await asyncio.sleep(delay)
            delay *= 2

    metadata = {
        "attempts": attempt,
        "hourly_present": bool(hourly_present),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # try to collect additional metadata if available
    if last_resp is not None:
        try:
            metadata["generation_ms"] = last_resp.GenerationTimeMilliseconds()
        except Exception:
            metadata["generation_ms"] = None
        try:
            metadata["model"] = last_resp.Model()
        except Exception:
            metadata["model"] = None
        try:
            metadata["timezone"] = last_resp.Timezone()
        except Exception:
            metadata["timezone"] = None
        try:
            metadata["utc_offset"] = last_resp.UtcOffsetSeconds()
        except Exception:
            metadata["utc_offset"] = None
        try:
            metadata["latitude"] = last_resp.Latitude()
            metadata["longitude"] = last_resp.Longitude()
        except Exception:
            metadata["latitude"] = None
            metadata["longitude"] = None
        try:
            metadata["elevation"] = last_resp.Elevation()
        except Exception:
            metadata["elevation"] = None

    return last_resp, metadata
