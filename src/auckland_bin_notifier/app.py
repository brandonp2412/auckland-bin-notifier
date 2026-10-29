from __future__ import annotations

import datetime as dt
import os
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from . import beszel_dm, matrix
from .sources import (
    SourceError,
    collection_types_from_ics_url,
    collection_types_from_property,
)
from .state import mark_sent, was_sent

TIMEZONE = ZoneInfo("Pacific/Auckland")


def state_path() -> Path:
    return Path(
        os.environ.get(
            "AUCKLAND_BIN_STATE",
            "~/.local/state/auckland-bin-notifier/state.json",
        )
    ).expanduser()


def cache_path() -> Path:
    return Path(
        os.environ.get(
            "AUCKLAND_BIN_ICS_CACHE",
            "~/.local/state/auckland-bin-notifier/latest.ics",
        )
    ).expanduser()


def collection_types_for_date(target: dt.date) -> set[str]:
    ics_url = os.environ.get("AUCKLAND_BIN_ICS_URL", "").strip()
    property_id = os.environ.get("AUCKLAND_BIN_PROPERTY_ID", "").strip()
    if ics_url:
        return collection_types_from_ics_url(ics_url, target, cache_path())
    if property_id:
        return collection_types_from_property(property_id, target, cache_path())
    raise SourceError(
        "set AUCKLAND_BIN_ICS_URL or AUCKLAND_BIN_PROPERTY_ID in "
        "~/.config/auckland-bin-notifier/config.env"
    )


def message_for(kinds: set[str], target: dt.date) -> str:
    today = dt.datetime.now(TIMEZONE).date()
    is_tomorrow = target == today + dt.timedelta(days=1)

    if kinds == {"rubbish", "recycling"}:
        if is_tomorrow:
            return "🗑️♻️ Heads up — rubbish + recycling tomorrow. Pop both bins out tonight!"
        if target == today:
            return "🗑️♻️ Bin day today — rubbish + recycling!"
        return f"🗑️♻️ Bin day {target.isoformat()} — rubbish + recycling."

    if kinds == {"rubbish"}:
        if is_tomorrow:
            return "🗑️ Heads up — rubbish tomorrow. Pop the bin out tonight!"
        if target == today:
            return "🗑️ Rubbish day today!"
        return f"🗑️ Rubbish day {target.isoformat()}."

    if kinds == {"recycling"}:
        if is_tomorrow:
            return "♻️ Heads up — recycling tomorrow. Pop the bin out tonight!"
        if target == today:
            return "♻️ Recycling day today!"
        return f"♻️ Recycling day {target.isoformat()}."

    return f"🗑️ Bin day {target.isoformat()} — {', '.join(sorted(kinds))}."


def _fetch_with_retries(target: dt.date, attempts: int = 3) -> set[str]:
    last_error: SourceError | OSError | None = None
    for attempt in range(attempts):
        try:
            return collection_types_for_date(target)
        except (SourceError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(3 * (attempt + 1))
    assert last_error is not None
    raise last_error


def _send_once(message: str, *, room_id: str | None = None) -> None:
    if room_id is None:
        matrix.send_message(message)
    else:
        matrix.send_message(message, room_id=room_id)


def default_target_date() -> dt.date:
    today = dt.datetime.now(TIMEZONE).date()
    return today + dt.timedelta(days=1)


def run(target: dt.date | None = None, *, dry_run: bool = False) -> str:
    target = target or default_target_date()
    kinds = _fetch_with_retries(target)

    if not kinds:
        result = f"No rubbish or recycling collection on {target.isoformat()}."
        print(result)
        return result

    message = message_for(kinds, target)
    fingerprint = f"{target.isoformat()}:{','.join(sorted(kinds))}"
    path = state_path()
    dm_env = os.environ.get("AUCKLAND_BIN_DM_ENV", "").strip()
    group_sent = was_sent(path, fingerprint)
    dm_sent = bool(dm_env) and was_sent(path, fingerprint, recipient="dm")
    if group_sent and (not dm_env or dm_sent):
        result = f"Already notified: {message}"
        print(result)
        return result

    if dry_run:
        print(f"DRY RUN: {message}")
        return message

    failures = []
    if not group_sent:
        try:
            _send_once(message)
            mark_sent(path, fingerprint)
        except (matrix.MatrixError, OSError) as exc:
            failures.append(f"group: {exc}")

    if dm_env and not dm_sent:
        try:
            beszel_dm.send_message(
                message,
                config_path=Path(dm_env).expanduser(),
                expected_user=os.environ["AUCKLAND_BIN_DM_USER_ID"],
                expected_room=os.environ["AUCKLAND_BIN_DM_ROOM_ID"],
                allow_unverified=os.environ.get(
                    "AUCKLAND_BIN_DM_IGNORE_UNVERIFIED_DEVICES", ""
                ).casefold() in {"1", "true", "yes"},
            )
            mark_sent(path, fingerprint, recipient="dm")
        except (KeyError, matrix.MatrixError, OSError) as exc:
            failures.append(f"Beszel DM: {exc}")

    if failures:
        raise matrix.MatrixError("; ".join(failures))
    print(f"Sent Matrix reminder to configured destinations: {message}")
    return message


def e2e_message_for(kinds: set[str], target: dt.date) -> str:
    if kinds == {"rubbish", "recycling"}:
        result = "rubbish + recycling"
    elif kinds:
        result = " + ".join(sorted(kinds))
    else:
        result = "no rubbish or recycling"
    return (
        "🧪 Auckland Bin Notifier — E2E test\n"
        "Source fetch ✓  Parser ✓  Matrix delivery test\n"
        f"Live result for {target.isoformat()}: {result}.\n"
        "Test only — reminder state is unchanged."
    )


def run_e2e(target: dt.date | None = None) -> str:
    target = target or default_target_date()
    kinds = _fetch_with_retries(target)
    room_id = os.environ.get("MATRIX_E2E_TEST_ROOM_ID", "").strip()
    if not room_id or not room_id.startswith("!") or ":" not in room_id:
        raise matrix.MatrixError(
            "MATRIX_E2E_TEST_ROOM_ID must be configured; refusing to send a test "
            "to the production Matrix room"
        )
    if room_id == os.environ.get("MATRIX_ROOM_ID"):
        raise matrix.MatrixError("Test room must differ from the production room")
    message = e2e_message_for(kinds, target)
    _send_once(message, room_id=room_id)
    print(f"Sent E2E Matrix test to {room_id}: {message}")
    return message
