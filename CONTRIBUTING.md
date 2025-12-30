# Contributing

Thanks for contributing! This file describes how to set up the repo locally, run tests and linters, and submit PRs.

## Local setup
1. Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install `uv` and sync pinned dependencies from `uv.lock`:

```bash
python -m pip install uv
uv sync
```

3. Install developer tools (ruff, pytest):

```bash
python -m pip install ruff pytest pytest-asyncio
```

## Running tests
- Run the full test suite:

```bash
pytest
```

- Run a single test file / test function:

```bash
pytest tests/test_weather.py::test_name
```

## Linting & formatting
- Check formatting and lint issues with Ruff:

```bash
ruff format --check .
ruff check .
```

- To auto-fix formatting issues:

```bash
ruff format .
```

## Running the server locally
- Start the MCP server for local testing:

```bash
python -m weather
```

- Use an MCP client (or call tools directly in test code) to exercise `get_forecast` and `save_raw_forecast`.

## Testing network-dependent behavior
- Tests use lightweight fake FlatBuffers objects to simulate API responses (see `tests/test_weather.py`).
- For deterministic tests of retry behavior, monkeypatch `make_open_meteo_request` to return responses that simulate missing/hourly blocks.

## Submitting changes
- Create a topic branch, run tests and linters locally, and open a PR against `main`.
- Include tests for new behavior and update `README.md`/`agents.md` as appropriate.

Thanks — small, well-tested changes are welcome!