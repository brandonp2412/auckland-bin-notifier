"""Provision the private, encrypted Matrix test room, never the live reminder room."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from nio import (
    AsyncClient,
    AsyncClientConfig,
    RoomCreateResponse,
    RoomGetStateResponse,
    RoomPreset,
    RoomPutStateResponse,
    RoomVisibility,
    UploadResponse,
)

from .cli import load_default_env
from .nio_transport import NioTransportError

ROOM_NAME = "🧪 Auckland Bins · E2E Lab"
ROOM_TOPIC = (
    "Private, end-to-end encrypted test space for Auckland Bin Notifier. "
    "Automated checks only; real bin reminders go to their usual room."
)
ROOM_ENV_KEY = "MATRIX_E2E_TEST_ROOM_ID"


def private_members(state: list[dict[str, object]], user_id: str) -> bool:
    members: set[str] = set()
    for event in state:
        content = event.get("content")
        if (
            event.get("type") == "m.room.member"
            and isinstance(content, dict)
            and content.get("membership") in ("join", "invite")
        ):
            members.add(str(event.get("state_key")))
    return members == {user_id, "@brandon:matrix.presley.nz"} or members == {user_id}


async def provision(avatar: Path) -> str:
    user_id = os.environ["MATRIX_USER_ID"]
    device_id = os.environ["MATRIX_DEVICE_ID"]
    homeserver = os.environ["MATRIX_HOMESERVER"]
    token = os.environ["MATRIX_ACCESS_TOKEN"]
    store = Path(os.environ["MATRIX_SDK_STORE_PATH"])
    client = AsyncClient(
        homeserver, user_id, store_path=str(store),
        config=AsyncClientConfig(store_sync_tokens=True),
    )
    try:
        client.restore_login(user_id, device_id, token)
        existing_id = os.environ.get(ROOM_ENV_KEY)
        if existing_id:
            room_id = existing_id
        else:
            response = await client.room_create(
                visibility=RoomVisibility.private,
                name=ROOM_NAME,
                topic=ROOM_TOPIC,
                preset=RoomPreset.private_chat,
                invite=(),
                initial_state=[
                    {
                        "type": "m.room.encryption", "state_key": "",
                        "content": {"algorithm": "m.megolm.v1.aes-sha2"},
                    },
                    {
                        "type": "m.room.history_visibility", "state_key": "",
                        "content": {"history_visibility": "joined"},
                    },
                    {
                        "type": "m.room.guest_access", "state_key": "",
                        "content": {"guest_access": "forbidden"},
                    },
                ],
            )
            if not isinstance(response, RoomCreateResponse):
                raise RuntimeError(f"Private room creation failed: {response}")
            room_id = response.room_id
            # Persist immediately so any subsequent avatar/upload failure cannot
            # lead to a duplicate room on the next provisioning attempt.
            local_config = Path.home() / ".config/auckland-bin-notifier/config.env"
            with local_config.open("a") as output:
                output.write(f"\n{ROOM_ENV_KEY}={room_id}\n")
            os.environ[ROOM_ENV_KEY] = room_id
        if existing_id:
            state = await client.room_get_state(room_id)
            if not isinstance(state, RoomGetStateResponse):
                raise RuntimeError(f"Cannot verify room membership: {state}")
            if not private_members(state.events, user_id):
                raise RuntimeError("Test room contains unexpected members")
            print(f"Verified existing private test room: {room_id}")
            return room_id
        with avatar.open("rb") as image:
            uploaded, _ = await client.upload(
                image, content_type="image/png", filename="auckland-bins-e2e.png",
                filesize=avatar.stat().st_size,
            )
        if not isinstance(uploaded, UploadResponse):
            raise NioTransportError(f"Room avatar upload failed: {uploaded}")
        updated = await client.room_put_state(
            room_id, "m.room.avatar", {"url": uploaded.content_uri},
        )
        if not isinstance(updated, RoomPutStateResponse):
            raise NioTransportError(f"Setting room avatar failed: {updated}")
        state = await client.room_get_state(room_id)
        if not isinstance(state, RoomGetStateResponse):
            raise NioTransportError(f"Cannot verify room membership: {state}")
        if not private_members(state.events, user_id):
            raise RuntimeError("Test room has a member other than the owner")
        if not any(
            event.get("type") == "m.room.encryption"
            and event.get("content", {}).get("algorithm") == "m.megolm.v1.aes-sha2"
            for event in state.events
        ):
            raise RuntimeError("Test room encryption state was not confirmed")
        print(f"Created/verified owner-only encrypted Matrix room: {room_id}")
        print(f"Avatar uploaded: {uploaded.content_uri}")
        return room_id
    finally:
        await client.close()


def main() -> None:
    load_default_env()
    if os.environ.get("MATRIX_TRANSPORT") != "nio":
        raise SystemExit("Provision the dedicated Matrix SDK device first")
    avatar = Path(__file__).parents[2] / "assets/auckland-bins-e2e-avatar.png"
    asyncio.run(provision(avatar))


if __name__ == "__main__":
    main()
