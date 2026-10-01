from types import SimpleNamespace

import pytest

from auckland_bin_notifier import matrix


def test_send_message_uses_mcp_when_configured(monkeypatch):
    calls = []
    monkeypatch.setenv("MATRIX_ROOM_ID", "!room:example.org")
    monkeypatch.setenv("MATRIX_MCP_URL", "http://127.0.0.1:8000/mcp")

    monkeypatch.setattr(
        matrix,
        "_send_via_mcp",
        lambda body, room_id, mcp_url, timeout: calls.append(
            (body, room_id, mcp_url, timeout)
        ),
    )
    monkeypatch.setattr(
        matrix,
        "_send_via_client_api",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("direct transport should not be used")
        ),
    )

    matrix.send_message("hello", timeout=3.0)

    assert calls == [
        ("hello", "!room:example.org", "http://127.0.0.1:8000/mcp", 3.0)
    ]


def test_send_message_uses_direct_api_without_mcp(monkeypatch):
    calls = []
    monkeypatch.setenv("MATRIX_ROOM_ID", "!room:example.org")
    monkeypatch.delenv("MATRIX_MCP_URL", raising=False)

    monkeypatch.setattr(
        matrix,
        "_send_via_client_api",
        lambda body, room_id, timeout: calls.append((body, room_id, timeout)),
    )
    monkeypatch.setattr(
        matrix,
        "_send_via_mcp",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("MCP transport should not be used")
        ),
    )

    matrix.send_message("hello", timeout=4.0)

    assert calls == [("hello", "!room:example.org", 4.0)]


def test_mcp_tool_error_survives_transport_cleanup(monkeypatch):
    class FakeTransport:
        async def __aenter__(self):
            return object(), object()

        async def __aexit__(self, exc_type, exc, traceback):
            if exc is not None:
                raise ExceptionGroup("transport cleanup", [exc])

    class FakeSession:
        def __init__(self, *args):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def initialize(self):
            pass

        async def call_tool(self, name, arguments):
            return SimpleNamespace(
                is_error=True,
                content=[SimpleNamespace(text="device is not verified")],
            )

    def fake_import(name):
        if name == "mcp":
            return SimpleNamespace(ClientSession=FakeSession)
        if name == "mcp.client.streamable_http":
            return SimpleNamespace(
                streamable_http_client=lambda url: FakeTransport()
            )
        raise ImportError(name)

    monkeypatch.setattr(matrix, "import_module", fake_import)

    with pytest.raises(matrix.MatrixError, match="device is not verified"):
        matrix._send_via_mcp(
            "hello",
            "!room:example.org",
            "http://127.0.0.1:8000/mcp",
            timeout=3.0,
        )
