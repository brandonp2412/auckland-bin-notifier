from __future__ import annotations

import json
import os
from pathlib import Path


def load_state(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def was_sent(path: Path, fingerprint: str) -> bool:
    return load_state(path).get("last_sent") == fingerprint


def mark_sent(path: Path, fingerprint: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"last_sent": fingerprint}, indent=2) + "\n")
    os.replace(tmp, path)
