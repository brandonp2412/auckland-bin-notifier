from __future__ import annotations

import asyncio
import json
import os
import time
from importlib import import_module
import urllib.parse
import urllib.request


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

    async def _send() -> None:
        async with streamable_http_client(mcp_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "send_message",
                    {"room_id": room_id, "body": body},
                )
                is_error = bool(
                    getattr(result, "isError", getattr(result, "is_error", False))
                )
                if is_error:
                    details = " ".join(
                        str(getattr(part, "text", ""))
                        for part in getattr(result, "content", [])
                        if getattr(part, "text", None)
                    ).strip()
                    raise MatrixError(
                        f"Matrix MCP send failed: {details or 'unknown MCP error'}"
                    )

    try:
        asyncio.run(asyncio.wait_for(_send(), timeout=timeout))
    except Exception as exc:
        if isinstance(exc, MatrixError):
            raise
        raise MatrixError(f"Matrix MCP send failed: {exc}") from exc


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


def send_message(body: str, timeout: float = 15.0) -> None:
    room_id = os.environ["MATRIX_ROOM_ID"]
    mcp_url = os.environ.get("MATRIX_MCP_URL", "").strip()
    if mcp_url:
        _send_via_mcp(body, room_id, mcp_url, timeout)
        return
    _send_via_client_api(body, room_id, timeout)
