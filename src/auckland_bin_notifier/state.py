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


def _sent_key(recipient: str) -> str:
    return "last_sent" if recipient == "group" else f"last_{recipient}_sent"


def was_sent(path: Path, fingerprint: str, *, recipient: str = "group") -> bool:
    return load_state(path).get(_sent_key(recipient)) == fingerprint


def mark_sent(path: Path, fingerprint: str, *, recipient: str = "group") -> None:
    state = load_state(path)
    state[_sent_key(recipient)] = fingerprint
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    os.replace(tmp, path)
