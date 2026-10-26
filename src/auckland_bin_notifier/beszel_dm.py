"""Encrypted direct reminders from the existing Beszel bot identity."""

from __future__ import annotations

import asyncio
from pathlib import Path

from .matrix import MatrixError
from .nio_transport import send_async


def _load_config(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        raise MatrixError(f"Cannot read Beszel Matrix configuration: {exc}") from exc
    config = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        config[key.strip()] = value.strip().strip('"').strip("'")
    return config


def send_message(
    body: str,
    *,
    config_path: Path,
    expected_user: str,
    expected_room: str,
) -> None:
    config = _load_config(config_path)
    if config.get("MATRIX_TRANSPORT") != "nio":
        raise MatrixError("Beszel account must use the encrypted Matrix SDK")
    if (
        config.get("MATRIX_USER_ID") != expected_user
        or config.get("MATRIX_ROOM_ID") != expected_room
    ):
        raise MatrixError("Beszel sender/DM differs from the verified identities")
    try:
        asyncio.run(
            asyncio.wait_for(
                send_async(
                    body,
                    homeserver=config["MATRIX_HOMESERVER"],
                    room_id=expected_room,
                    user_id=expected_user,
                    device_id=config["MATRIX_DEVICE_ID"],
                    access_token=config["MATRIX_ACCESS_TOKEN"],
                    store_path=Path(config["MATRIX_SDK_STORE_PATH"]).expanduser(),
                    allow_unverified=config.get(
                        "MATRIX_IGNORE_UNVERIFIED_DEVICES", ""
                    ).casefold() in {"1", "true", "yes"},
                ),
                timeout=30.0,
            )
        )
    except Exception as exc:
        raise MatrixError(f"Beszel encrypted DM failed: {exc}") from exc
