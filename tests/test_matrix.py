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
