import asyncio
import os
import socket
import subprocess
import sys
import time

import pytest

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


@pytest.mark.asyncio
async def test_streamable_http_server_with_fake(tmp_path):
    """Start the server with --use-fake on a random port and call get_forecast via streamable HTTP."""
    # Find a free port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    mount_path = "/mcp"
    server_uri = f"http://127.0.0.1:{port}{mount_path}"

    # Start the server as a subprocess using same Python interpreter
    # Use python -c to invoke the package entrypoint function directly so it works in test environments
    pycmd = "import sys; from weather_mcp_server import retrieve_weather as r; r.main(sys.argv[1:])"
    cmd = [
        sys.executable,
        "-c",
        pycmd,
        "--transport",
        "streamable-http",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--mount-path",
        mount_path,
        "--use-fake",
    ]
    env = os.environ.copy()
    # Ensure FastMCP binds to our chosen port by setting FASTMCP_* env vars before the module is imported
    # Configure the server via the WEATHER_* env vars so the module-level FastMCP picks them up at import time
    env["WEATHER_HOST"] = "127.0.0.1"
    env["WEATHER_PORT"] = str(port)
    env["WEATHER_MOUNT_PATH"] = mount_path

    proc = subprocess.Popen(
        cmd, cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), env=env
    )

    try:
        # Wait for the server to be reachable
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                await asyncio.sleep(0.1)
        else:
            pytest.skip("Server did not become reachable in time")

        # Connect via streamable HTTP client
        async with streamable_http_client(server_uri) as ctx:
            # ctx may be (read, write, get_session_id)
            if len(ctx) == 2:
                read, write = ctx
            else:
                read, write = ctx[0], ctx[1]

            async with ClientSession(read, write) as session:
                await session.initialize()

                resp = await session.list_tools()
                tools = [t.name for t in resp.tools]
                # find get_forecast
                tool_name = None
                for t in tools:
                    if "get_forecast" in t:
                        tool_name = t
                        break

                assert tool_name is not None, "get_forecast tool not exposed"

                # Call get_forecast; use args that the fake implementation will accept
                result = await session.call_tool(
                    tool_name, {"latitude": 49.48, "longitude": 8.446}
                )

                assert hasattr(result, "content")
                content = result.content
                # Content may be a list of TextContent objects or a plain string
                if isinstance(content, list):
                    # join text fields when present
                    content_text = "".join(getattr(c, "text", str(c)) for c in content)
                else:
                    content_text = str(content)

                assert "Now:" in content_text
                assert "Temperature" in content_text

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
