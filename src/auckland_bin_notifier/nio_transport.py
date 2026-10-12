"""Direct Matrix SDK transport with a dedicated persistent E2EE device."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from nio import (
    AsyncClient,
    AsyncClientConfig,
    KeysUploadResponse,
    RoomSendResponse,
    SyncResponse,
)


class NioTransportError(RuntimeError):
    """A Matrix SDK send failed or the dedicated device is not provisioned."""


def _is_truthy(value: str) -> bool:
    return value.casefold() in {"1", "true", "yes"}


def _validate_store(path: Path, user_id: str, device_id: str) -> None:
    # A process must never clone or open the live Matrix MCP's Olm identity.
    # Independent devices have independent Olm ratchets and SQLite stores.
    if not device_id or not user_id:
        raise NioTransportError("Matrix SDK user and device ID are required")
    expected = path / f"{user_id}_{device_id}.db"
    if not expected.is_file():
        raise NioTransportError(
            "Matrix SDK device not provisioned in its own crypto store; "
            "refusing to invent or clone the active MCP encryption identity"
        )
    if (path / "nio_mcp.db").exists():
        raise NioTransportError("The SDK store must not be the live Matrix MCP store")


async def send_async(
    body: str,
    *,
    homeserver: str,
    room_id: str,
    user_id: str,
    device_id: str,
    access_token: str,
    store_path: Path,
    allow_unverified: bool = False,
    timeout: float = 30.0,
) -> str:
    _validate_store(store_path, user_id, device_id)
    client = AsyncClient(
        homeserver,
        user_id,
        store_path=str(store_path),
        config=AsyncClientConfig(store_sync_tokens=True),
    )
    try:
        client.restore_login(user_id=user_id, device_id=device_id, access_token=access_token)
        # Limit the sync to the one room this notifier needs. A full account
        # sync here would fetch hundreds of unrelated Matrix conversations.
        sync_filter = {
            "room": {
                "rooms": [room_id],
                "timeline": {"limit": 0},
                "state": {"lazy_load_members": False},
            },
            "presence": {"types": []},
            "account_data": {"types": []},
        }
        if client.should_upload_keys:
            upload = await client.keys_upload()
            if not isinstance(upload, KeysUploadResponse):
                raise NioTransportError(f"Matrix device-key upload failed: {upload}")
        sync_response = await client.sync(
            timeout=0,
            full_state=True,
            sync_filter=sync_filter,
        )
        if not isinstance(sync_response, SyncResponse):
            raise NioTransportError(f"Matrix sync failed: {sync_response}")
        room = client.rooms.get(room_id)
        if room is None or not room.encrypted:
            raise NioTransportError("Expected an encrypted Matrix room; refusing plaintext")
        response = await client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": body},
            ignore_unverified_devices=allow_unverified,
        )
        if not isinstance(response, RoomSendResponse) or not response.event_id:
            raise NioTransportError(f"Matrix SDK did not confirm delivery: {response}")
        return response.event_id
    finally:
        await client.close()


def send_message(body: str, *, timeout: float = 30.0, room_id: str | None = None) -> str:
    try:
        user_id = os.environ["MATRIX_USER_ID"]
        device_id = os.environ["MATRIX_DEVICE_ID"]
        access_token = os.environ["MATRIX_ACCESS_TOKEN"]
        target_room = room_id if room_id is not None else os.environ["MATRIX_ROOM_ID"]
        homeserver = os.environ["MATRIX_HOMESERVER"]
        store_path = Path(os.environ["MATRIX_SDK_STORE_PATH"]).expanduser()
    except KeyError as exc:
        raise NioTransportError(f"Missing Matrix SDK configuration: {exc}") from exc
    try:
        return asyncio.run(
            asyncio.wait_for(
                send_async(
                    body,
                    homeserver=homeserver,
                    room_id=target_room,
                    user_id=user_id,
                    device_id=device_id,
                    access_token=access_token,
                    store_path=store_path,
                    allow_unverified=_is_truthy(
                        os.environ.get("MATRIX_IGNORE_UNVERIFIED_DEVICES", "")
                    ),
                    timeout=timeout,
                ),
                timeout=timeout,
            )
        )
    except NioTransportError:
        raise
    except Exception as exc:
        raise NioTransportError(f"Matrix SDK send failed: {exc}") from exc
