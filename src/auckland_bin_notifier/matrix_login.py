"""One-time login that gives the notifier its own encrypted Matrix device."""

from __future__ import annotations

import asyncio
import getpass
import os
from pathlib import Path

from nio import (
    AsyncClient,
    AsyncClientConfig,
    KeysUploadResponse,
    LoginResponse,
)

from .cli import load_default_env


async def _login(homeserver: str, user_id: str, password: str, store_path: Path) -> LoginResponse:
    client = AsyncClient(
        homeserver,
        user_id,
        store_path=str(store_path),
        config=AsyncClientConfig(store_sync_tokens=True),
    )
    try:
        result = await client.login(password=password, device_name="Auckland Bin Notifier")
        successful_login = result if isinstance(result, LoginResponse) else None
        if successful_login is None:
            raise RuntimeError(f"Matrix device login failed: {result}")
        if client.should_upload_keys:
            result_keys = await client.keys_upload()
            if not isinstance(result_keys, KeysUploadResponse):
                raise RuntimeError(f"Matrix key upload failed: {result_keys}")
        return successful_login
    finally:
        await client.close()


def main() -> int:
    load_default_env()
    home = Path.home()
    cfg = home / ".config/auckland-bin-notifier/matrix-sdk.env"
    if cfg.exists():
        raise SystemExit("Matrix SDK device already configured; leaving existing credentials unchanged")
    homeserver = os.environ.get("MATRIX_HOMESERVER", "https://matrix.presley.nz")
    user_id = os.environ.get("MATRIX_USER_ID", "@brandon:matrix.presley.nz")
    room_id = os.environ.get("MATRIX_ROOM_ID", "")
    if not room_id:
        raise SystemExit("MATRIX_ROOM_ID is required")
    store = home / ".local/state/auckland-bin-notifier/matrix-sdk"
    if store.exists() and list(store.iterdir()):
        raise SystemExit("Matrix SDK crypto store is not empty; refusing to replace it")
    store.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(store, 0o700)
    password = getpass.getpass(f"One-time Matrix password for {user_id}: ")
    if not password:
        raise SystemExit("Password is required to create an independent device")
    login = asyncio.run(_login(homeserver, user_id, password, store))
    password = ""
    if not (store / f"{login.user_id}_{login.device_id}.db").is_file():
        raise SystemExit("Matrix login did not persist the expected encryption store")
    cfg.parent.mkdir(parents=True, exist_ok=True)
    lines = (
        "MATRIX_TRANSPORT=nio\n"
        f"MATRIX_HOMESERVER={homeserver}\n"
        f"MATRIX_USER_ID={login.user_id}\n"
        f"MATRIX_DEVICE_ID={login.device_id}\n"
        f"MATRIX_ACCESS_TOKEN={login.access_token}\n"
        f"MATRIX_SDK_STORE_PATH={store}\n"
    )
    fd = os.open(cfg, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(lines)
    print(f"Provisioned independent Matrix SDK device {login.device_id} in {cfg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
