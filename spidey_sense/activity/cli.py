"""Command-line interface for the teammate activity store."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .store import VALID_STATUSES, ActivityNotFoundError, ActivityStore, ActivityStoreError


DEFAULT_STORE = Path(".spidey-sense/activity.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spidey-sense-activity",
        description="Track each teammate's current files and status in a local JSON store.",
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=DEFAULT_STORE,
        help=f"Activity JSON path (default: {DEFAULT_STORE}).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_parser = subparsers.add_parser("set", help="Create or replace a teammate activity.")
    set_parser.add_argument("teammate", help="Stable teammate name or identifier.")
    set_parser.add_argument("status", choices=VALID_STATUSES)
    set_parser.add_argument("files", nargs="+", help="Repository-relative file paths.")

    status_parser = subparsers.add_parser("status", help="Update status while retaining files.")
    status_parser.add_argument("teammate")
    status_parser.add_argument("status", choices=VALID_STATUSES)

    get_parser = subparsers.add_parser("get", help="Show one teammate's activity.")
    get_parser.add_argument("teammate")

    subparsers.add_parser("list", help="Show the complete activity store.")

    remove_parser = subparsers.add_parser("remove", help="Remove a teammate's activity.")
    remove_parser.add_argument("teammate")
    return parser


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=False))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = ActivityStore(args.store)

    try:
        if args.command == "set":
            _print_json(store.upsert(args.teammate, args.files, args.status).to_dict())
        elif args.command == "status":
            _print_json(store.update_status(args.teammate, args.status).to_dict())
        elif args.command == "get":
            _print_json(store.get(args.teammate).to_dict())
        elif args.command == "list":
            _print_json(store.snapshot())
        elif args.command == "remove":
            removed = store.remove(args.teammate)
            _print_json({"teammate": args.teammate.strip(), "removed": removed})
        else:  # pragma: no cover - argparse guarantees the command.
            raise AssertionError(f"unhandled command: {args.command}")
    except ActivityNotFoundError as exc:
        print(f"spidey-sense-activity: error: {exc}", file=sys.stderr)
        return 1
    except ActivityStoreError as exc:
        print(f"spidey-sense-activity: error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
