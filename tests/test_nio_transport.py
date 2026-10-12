"""Safety and successful encrypted sends through a dedicated Matrix SDK device."""

import asyncio
from types import SimpleNamespace

import pytest

from auckland_bin_notifier import nio_transport


def test_rejects_missing_crypto_store(tmp_path):
    with pytest.raises(nio_transport.NioTransportError, match="not provisioned"):
        nio_transport._validate_store(tmp_path, "@owner:example.org", "DEVICE")


def test_rejects_shared_mcp_store(tmp_path):
    (tmp_path / "@owner:example.org_DEVICE.db").touch()
    (tmp_path / "nio_mcp.db").touch()
    with pytest.raises(nio_transport.NioTransportError, match="live Matrix MCP store"):
        nio_transport._validate_store(tmp_path, "@owner:example.org", "DEVICE")


def test_sends_encrypted_and_requires_event_id(monkeypatch, tmp_path):
    (tmp_path / "@owner:example.org_DEVICE.db").touch()
    observed = {}

    class FakeSync:
        pass

    class FakeSent:
        def __init__(self, event_id):
            self.event_id = event_id

    class FakeClient:
        def __init__(self, homeserver, user_id, store_path, config):
            assert homeserver == "https://matrix.example.org"
            assert user_id == "@owner:example.org"
            assert store_path == str(tmp_path)
            self.rooms = {"!room:example.org": SimpleNamespace(encrypted=True)}
            self.should_upload_keys = False

        def restore_login(self, **kwargs):
            observed["credentials"] = (kwargs["user_id"], kwargs["device_id"])

        async def sync(self, **kwargs):
            observed["sync_filter"] = kwargs["sync_filter"]
            return FakeSync()

        async def room_send(self, **kwargs):
            observed["send"] = kwargs
            return FakeSent("$sent:example.org")

        async def close(self):
            observed["closed"] = True

    monkeypatch.setattr(nio_transport, "AsyncClient", FakeClient)
    monkeypatch.setattr(nio_transport, "SyncResponse", FakeSync)
    monkeypatch.setattr(nio_transport, "RoomSendResponse", FakeSent)
    result = asyncio.run(nio_transport.send_async(
        "Bin day", homeserver="https://matrix.example.org",
        room_id="!room:example.org", user_id="@owner:example.org",
        device_id="DEVICE", access_token="test-token", store_path=tmp_path,
        allow_unverified=True,
    ))
    assert result == "$sent:example.org"
    assert observed["credentials"] == ("@owner:example.org", "DEVICE")
    assert observed["send"]["ignore_unverified_devices"] is True
    assert observed["sync_filter"]["room"]["rooms"] == ["!room:example.org"]
    assert observed["closed"] is True


def test_refuses_plaintext_even_if_sync_works(monkeypatch, tmp_path):
    (tmp_path / "@owner:example.org_DEVICE.db").touch()

    class FakeSync:
        pass

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.rooms = {"!room:example.org": SimpleNamespace(encrypted=False)}
            self.should_upload_keys = False

        def restore_login(self, **kwargs):
            pass

        async def sync(self, **kwargs):
            return FakeSync()

        async def room_send(self, **kwargs):
            raise AssertionError("plaintext message must never be sent")

        async def close(self):
            pass

    monkeypatch.setattr(nio_transport, "AsyncClient", FakeClient)
    monkeypatch.setattr(nio_transport, "SyncResponse", FakeSync)
    with pytest.raises(nio_transport.NioTransportError, match="refusing plaintext"):
        asyncio.run(nio_transport.send_async(
            "Bin day", homeserver="https://matrix.example.org",
            room_id="!room:example.org", user_id="@owner:example.org",
            device_id="DEVICE", access_token="test-token", store_path=tmp_path,
        ))
