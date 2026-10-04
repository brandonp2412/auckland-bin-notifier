from __future__ import annotations

import datetime as dt
import os
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from . import matrix
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
    if target == today + dt.timedelta(days=1):
        prefix = "Bins are due tomorrow"
    elif target == today:
        prefix = "Bin day today"
    else:
        prefix = f"Bin day {target.isoformat()}"

    if kinds == {"rubbish", "recycling"}:
        return f"{prefix}: rubbish and recycling. Put both bins out tonight."
    if kinds == {"rubbish"}:
        return f"{prefix}: rubbish. Put the rubbish bin out tonight."
    if kinds == {"recycling"}:
        return f"{prefix}: recycling. Put the recycling bin out tonight."
    return f"{prefix}: {', '.join(sorted(kinds))}."


def _fetch_with_retries(target: dt.date, attempts: int = 3) -> set[str]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return collection_types_for_date(target)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(3 * (attempt + 1))
    assert last_error is not None
    raise last_error


def default_target_date() -> dt.date:
    return dt.datetime.now(TIMEZONE).date() + dt.timedelta(days=1)


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
    if was_sent(path, fingerprint):
        result = f"Already notified: {message}"
        print(result)
        return result

    if dry_run:
        print(f"DRY RUN: {message}")
        return message

    matrix.send_message(message)
    mark_sent(path, fingerprint)
    print(f"Sent Matrix notification: {message}")
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
    message = e2e_message_for(kinds, target)
    matrix.send_message(message)
    print(f"Sent E2E Matrix test: {message}")
    return message
