from __future__ import annotations

import sys
import types


try:
    import docker  # noqa: F401
except ModuleNotFoundError:
    docker_stub = types.ModuleType("docker")

    class DockerClient:
        pass

    def from_env():
        raise RuntimeError("docker package is not installed in this test environment")

    docker_stub.DockerClient = DockerClient
    docker_stub.from_env = from_env
    sys.modules["docker"] = docker_stub

try:
    import mcp  # noqa: F401
except ModuleNotFoundError:
    mcp_stub = types.ModuleType("mcp")
    mcp_client_stub = types.ModuleType("mcp.client")
    mcp_stdio_stub = types.ModuleType("mcp.client.stdio")
    mcp_types_stub = types.ModuleType("mcp.types")

    class StdioServerParameters:
        def __init__(self, *, command: str, args: list[str] | None = None) -> None:
            self.command = command
            self.args = args or []

    class ClientSession:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def initialize(self) -> None:
            return None

        async def call_tool(self, *args, **kwargs):
            return types.SimpleNamespace(content=[], isError=False)

        async def list_tools(self):
            return types.SimpleNamespace(tools=[])

    class TextContent:
        text: str

    class _StdioContext:
        async def __aenter__(self):
            return None, None

        async def __aexit__(self, *args) -> None:
            return None

    def stdio_client(*args, **kwargs):
        return _StdioContext()

    mcp_stub.ClientSession = ClientSession
    mcp_stub.StdioServerParameters = StdioServerParameters
    mcp_stdio_stub.stdio_client = stdio_client
    mcp_types_stub.TextContent = TextContent
    sys.modules["mcp"] = mcp_stub
    sys.modules["mcp.client"] = mcp_client_stub
    sys.modules["mcp.client.stdio"] = mcp_stdio_stub
    sys.modules["mcp.types"] = mcp_types_stub

try:
    import celery  # noqa: F401
except ModuleNotFoundError:
    celery_stub = types.ModuleType("celery")

    class Celery:
        def __init__(self, *args, **kwargs) -> None:
            self.conf: dict[str, object] = {}
            self.sent_tasks: list[dict[str, object]] = []

        def autodiscover_tasks(self, *args, **kwargs) -> None:
            return None

        def send_task(self, name: str, **kwargs) -> None:
            self.sent_tasks.append({"name": name, **kwargs})

    celery_stub.Celery = Celery
    sys.modules["celery"] = celery_stub
