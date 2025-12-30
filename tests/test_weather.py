import os
import sys
import pytest

# Ensure project root is on sys.path so tests can import `weather`
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from weather_mcp_server.retrieve_weather import _describe_weather_code, make_open_meteo_request, get_forecast
from openmeteo_sdk.Variable import Variable

# Simple unit tests for WEATHER_CODE mapping


def test_describe_weather_code_known_unknown():
    assert _describe_weather_code(77) == "Snow grains"
    assert _describe_weather_code(None) == "Unknown"
    assert _describe_weather_code(9999) == "Code 9999"


@pytest.mark.asyncio
async def test_make_open_meteo_request_handles_exception(monkeypatch):
    class BrokenClient:
        async def weather_api(self, url, params=None):
            raise RuntimeError("network")

    async def fake_client():
        return BrokenClient()

    # Monkeypatch the AsyncClient constructor to return our broken client
    monkeypatch.setattr("openmeteo_requests.AsyncClient", lambda: BrokenClient())

    res = await make_open_meteo_request(0.0, 0.0)
    assert res is None


# Build light-weight fake FlatBuffers-like objects for get_forecast
class FakeVar:
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


class FakeBlock:
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


class FakeResponse:
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


@pytest.mark.asyncio
async def test_get_forecast_formats_sections(monkeypatch):
    # Make a fake current block with temperature and weather_code
    cur_vars = [
        FakeVar(Variable.temperature, value=5.0),
        FakeVar(Variable.weather_code, value=1),
        FakeVar(Variable.wind_speed, value=10.0),
        FakeVar(Variable.wind_direction, value=90.0),
    ]
    current = FakeBlock(cur_vars)

    # Daily: temp max (agg=2), temp min (agg=1), precip
    daily_vars = [
        FakeVar(Variable.temperature, values=[6.0, 7.0, 5.5], agg=2),
        FakeVar(Variable.temperature, values=[0.0, -1.0, -2.0], agg=1),
        FakeVar(Variable.precipitation, values=[0.0, 1.2, 0.0]),
    ]
    daily = FakeBlock(daily_vars, time=1609459200, interval=86400)

    # Hourly: temps, precip, winds (small sample)
    hourly_vars = [
        FakeVar(Variable.temperature, values=[1.0] * 24),
        FakeVar(Variable.precipitation, values=[0.0] * 24),
        FakeVar(Variable.wind_speed, values=[3.0] * 24),
    ]
    hourly = FakeBlock(hourly_vars, time=1609459200, interval=3600)

    fake_resp = FakeResponse(current, daily, hourly, utc_offset=0)

    # Monkeypatch make_open_meteo_request to return our fake response list
    async def fake_make(lat, lon, params=None):
        return [fake_resp]

    monkeypatch.setattr("weather_mcp_server.weather.make_open_meteo_request", fake_make)

    out = await get_forecast(49.48, 8.446)

    # Check key sections are present
    assert "Now:" in out
    assert "Daily Forecast:" in out
    assert "Hourly Forecast (next 24h):" in out
    # Check some known values appear
    assert "Temperature: 5.0" in out
    assert "High 6.0" in out
    assert "2021-01-01" in out or "2021-01-02" in out


@pytest.mark.asyncio
async def test_get_forecast_handles_none():
    async def fake_none(lat, lon, params=None):
        return None

    import weather_mcp_server.retrieve_weather as w

    original = w.make_open_meteo_request
    w.make_open_meteo_request = fake_none
    try:
        out = await w.get_forecast(0.0, 0.0)
        assert "Unable to fetch" in out
    finally:
        w.make_open_meteo_request = original


@pytest.mark.asyncio
async def test_save_raw_forecast_creates_file(tmp_path, monkeypatch):
    # Reuse fake response from earlier test
    cur_vars = [
        FakeVar(Variable.temperature, value=5.0),
        FakeVar(Variable.weather_code, value=1),
    ]
    current = FakeBlock(cur_vars)

    daily_vars = [
        FakeVar(Variable.temperature, values=[6.0, 7.0, 5.5], agg=2),
        FakeVar(Variable.temperature, values=[0.0, -1.0, -2.0], agg=1),
        FakeVar(Variable.precipitation, values=[0.0, 1.2, 0.0]),
    ]
    daily = FakeBlock(daily_vars, time=1609459200, interval=86400)

    hourly_vars = [
        FakeVar(Variable.temperature, values=[1.0] * 24),
        FakeVar(Variable.precipitation, values=[0.0] * 24),
        FakeVar(Variable.wind_speed, values=[3.0] * 24),
    ]
    hourly = FakeBlock(hourly_vars, time=1609459200, interval=3600)

    fake_resp = FakeResponse(current, daily, hourly, utc_offset=0)

    async def fake_make(lat, lon, params=None):
        return [fake_resp]

    monkeypatch.setattr("weather_mcp_server.weather.make_open_meteo_request", fake_make)

    # Run the save_raw_forecast tool and ensure file created
    from weather_mcp_server.retrieve_weather import save_raw_forecast

    fname = await save_raw_forecast(49.48, 8.446)
    assert fname.startswith("data/")
    # The file should exist and contain the header "Now:"
    with open(fname, "r", encoding="utf-8") as fh:
        content = fh.read()
    assert "Now:" in content
    # cleanup
    try:
        os.remove(fname)
    except OSError:
        pass


@pytest.mark.asyncio
async def test_retry_when_hourly_missing_then_present(monkeypatch):
    # Create a response with no hourly (empty block) and then a full response
    cur_vars = [FakeVar(Variable.temperature, value=5.0)]
    current = FakeBlock(cur_vars)

    daily_vars = [
        FakeVar(Variable.temperature, values=[6.0, 7.0, 5.5], agg=2),
        FakeVar(Variable.temperature, values=[0.0, -1.0, -2.0], agg=1),
        FakeVar(Variable.precipitation, values=[0.0, 1.2, 0.0]),
    ]
    daily = FakeBlock(daily_vars, time=1609459200, interval=86400)

    # Response without hourly (empty variables)
    hourly_empty = FakeBlock([], time=1609459200, interval=3600)
    resp_no_hourly = FakeResponse(current, daily, hourly_empty, utc_offset=0)

    # Response with hourly
    hourly_vars = [
        FakeVar(Variable.temperature, values=[1.0] * 24),
        FakeVar(Variable.precipitation, values=[0.0] * 24),
        FakeVar(Variable.wind_speed, values=[3.0] * 24),
    ]
    hourly_full = FakeBlock(hourly_vars, time=1609459200, interval=3600)
    resp_with_hourly = FakeResponse(current, daily, hourly_full, utc_offset=0)

    seq = [[resp_no_hourly], [resp_with_hourly]]

    async def fake_make(lat, lon, params=None):
        return seq.pop(0)

    monkeypatch.setattr("weather_mcp_server.weather.make_open_meteo_request", fake_make)

    from weather_mcp_server.retrieve_weather import save_raw_forecast

    fname = await save_raw_forecast(49.48, 8.446)
    assert fname.startswith("data/")
    with open(fname, "r", encoding="utf-8") as fh:
        content = fh.read()
    assert "Hourly present: True" in content
    assert "Attempts: 2" in content
    assert "Hourly Forecast (next 24h):" in content

    try:
        os.remove(fname)
    except OSError:
        pass


@pytest.mark.asyncio
async def test_retry_exhausted_hourly_missing(monkeypatch):
    # Always return a response with no hourly
    cur_vars = [FakeVar(Variable.temperature, value=5.0)]
    current = FakeBlock(cur_vars)
    daily_vars = [
        FakeVar(Variable.temperature, values=[6.0, 7.0, 5.5], agg=2),
        FakeVar(Variable.temperature, values=[0.0, -1.0, -2.0], agg=1),
        FakeVar(Variable.precipitation, values=[0.0, 1.2, 0.0]),
    ]
    daily = FakeBlock(daily_vars, time=1609459200, interval=86400)
    hourly_empty = FakeBlock([], time=1609459200, interval=3600)
    resp_no_hourly = FakeResponse(current, daily, hourly_empty, utc_offset=0)

    async def fake_make(lat, lon, params=None):
        return [resp_no_hourly]

    monkeypatch.setattr("weather_mcp_server.weather.make_open_meteo_request", fake_make)

    from weather_mcp_server.retrieve_weather import save_raw_forecast

    fname = await save_raw_forecast(49.48, 8.446)
    with open(fname, "r", encoding="utf-8") as fh:
        content = fh.read()
    assert "Hourly present: False" in content
    assert "Attempts: 3" in content
    assert "Hourly forecast: not available." in content

    try:
        os.remove(fname)
    except OSError:
        pass
