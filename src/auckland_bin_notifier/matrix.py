from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.parse
import urllib.request
from importlib import import_module


class MatrixError(RuntimeError):
    pass


def _send_via_mcp(body: str, room_id: str, mcp_url: str, timeout: float) -> None:
    try:
        ClientSession = import_module("mcp").ClientSession
        streamable_http_client = import_module(
            "mcp.client.streamable_http"
        ).streamable_http_client
    except ImportError as exc:
        raise MatrixError(
            "MATRIX_MCP_URL is configured but the Matrix MCP client dependency is not installed"
        ) from exc

    allow_unverified = os.environ.get("MATRIX_IGNORE_UNVERIFIED_DEVICES", "").lower() in ("1", "true", "yes")

    async def _send():
        async with (
            streamable_http_client(mcp_url) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            arguments = {"room_id": room_id, "body": body}
            if allow_unverified:
                arguments["ignore_unverified_devices"] = True
            return await session.call_tool("send_message", arguments)

    try:
        result = asyncio.run(asyncio.wait_for(_send(), timeout=timeout))
    except Exception as exc:
        if isinstance(exc, MatrixError):
            raise
        raise MatrixError(f"Matrix MCP send failed: {exc}") from exc

    is_error = bool(
        getattr(result, "isError", getattr(result, "is_error", False))
    )
    details = " ".join(
        str(getattr(part, "text", ""))
        for part in getattr(result, "content", [])
        if getattr(part, "text", None)
    ).strip()
    if is_error:
        raise MatrixError(f"Matrix MCP send failed: {details or 'unknown MCP error'}")
    # Only a confirmed event ID counts as a delivered reminder.
    try:
        payload = json.loads(details)
    except (json.JSONDecodeError, TypeError) as exc:
        raise MatrixError(f"Unexpected Matrix MCP response: {details[:300]}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("event_id"), str):
        raise MatrixError(f"Matrix MCP did not confirm delivery: {details[:300]}")


def _send_via_client_api(body: str, room_id: str, timeout: float) -> None:
    homeserver = os.environ["MATRIX_HOMESERVER"].rstrip("/")
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


def send_message(body: str, timeout: float = 30.0) -> None:
    transport = os.environ.get("MATRIX_TRANSPORT", "").strip().lower()
    if transport == "nio":
        from .nio_transport import NioTransportError
        from .nio_transport import send_message as nio_send

        try:
            nio_send(body, timeout=timeout)
        except NioTransportError as exc:
            raise MatrixError(str(exc)) from exc
        return
    if transport and transport != "legacy":
        raise MatrixError(f"Unknown MATRIX_TRANSPORT: {transport}")
    room_id = os.environ["MATRIX_ROOM_ID"]
    mcp_url = os.environ.get("MATRIX_MCP_URL", "").strip()
    if mcp_url:
        _send_via_mcp(body, room_id, mcp_url, timeout)
        return
    _send_via_client_api(body, room_id, timeout)
