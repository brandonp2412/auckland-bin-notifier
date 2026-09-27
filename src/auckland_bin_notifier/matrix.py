from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request


class MatrixError(RuntimeError):
    pass


def send_message(body: str, timeout: float = 15.0) -> None:
    homeserver = os.environ["MATRIX_HOMESERVER"].rstrip("/")
    room_id = os.environ["MATRIX_ROOM_ID"]
    access_token = os.environ["MATRIX_ACCESS_TOKEN"]

    txn_id = f"auckland-bin-notifier-{int(time.time() * 1000)}-{os.getpid()}"
    room = urllib.parse.quote(room_id, safe="")
    txn = urllib.parse.quote(txn_id, safe="")
    url = f"{homeserver}/_matrix/client/v3/rooms/{room}/send/m.room.message/{txn}"
    payload = json.dumps({"msgtype": "m.text", "body": body}).encode()
    request = urllib.request.Request(
        url,
        data=payload,
        method="PUT",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            if response.status // 100 != 2:
                raise MatrixError(f"Matrix send returned HTTP {response.status}")
    except Exception as exc:
        if isinstance(exc, MatrixError):
            raise
        raise MatrixError(f"Matrix send failed: {exc}") from exc
