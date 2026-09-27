from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

from .app import run, run_e2e


def load_env_file(path: Path) -> None:
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_default_env() -> None:
    config_dir = Path.home() / ".config/auckland-bin-notifier"
    for path in (
        Path.cwd() / ".env",
        config_dir / "matrix.env",
        config_dir / "config.env",
    ):
        load_env_file(path)


def main(argv: list[str] | None = None) -> int:
    load_default_env()
    parser = argparse.ArgumentParser(
        description="Notify Matrix when Auckland Council rubbish/recycling is due."
    )
    parser.add_argument("--date", help="Check YYYY-MM-DD instead of tomorrow")
    parser.add_argument("--dry-run", action="store_true", help="Fetch/parse only; do not send Matrix")
    parser.add_argument(
        "--e2e-test",
        action="store_true",
        help="Fetch/parse live data and send a test Matrix message without updating reminder state",
    )
    parser.add_argument("--property-id", help="Override AUCKLAND_BIN_PROPERTY_ID for this run")
    parser.add_argument("--ics-url", help="Override AUCKLAND_BIN_ICS_URL for this run")
    args = parser.parse_args(argv)

    if args.property_id:
        os.environ["AUCKLAND_BIN_PROPERTY_ID"] = args.property_id
    if args.ics_url:
        os.environ["AUCKLAND_BIN_ICS_URL"] = args.ics_url

    if args.dry_run and args.e2e_test:
        parser.error("--dry-run and --e2e-test cannot be used together")

    try:
        target = dt.date.fromisoformat(args.date) if args.date else None
        if args.e2e_test:
            run_e2e(target)
        else:
            run(target, dry_run=args.dry_run)
        return 0
    except Exception as exc:
        print(f"auckland-bin-notifier: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
