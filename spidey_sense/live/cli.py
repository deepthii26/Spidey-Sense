"""CLI access to live telemetry and the human directive inbox."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .directives import DirectiveDispatchError, DirectiveDispatcher, DirectiveStore, DirectiveStoreError
from .telemetry import LiveTelemetryCollector, TelemetryError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spidey-sense-live",
        description="Inspect live agent/Git telemetry and manage human directives.",
    )
    parser.add_argument("--repository", type=Path, default=Path("."))
    parser.add_argument(
        "--directives", type=Path, default=Path(".spidey-sense/directives.json")
    )
    parser.add_argument("--pretty", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("snapshot", help="Print current Git and agent telemetry.")
    commands.add_parser("inbox", help="Print queued and delivered directives.")

    send = commands.add_parser("send", help="Create a directive for a teammate or agent.")
    send.add_argument("teammate")
    send.add_argument("message")
    send.add_argument("--provider", choices=("inbox", "codex", "claude", "entire"), default="inbox")
    send.add_argument("--session-id")
    send.add_argument("--deliver-now", action="store_true")

    acknowledge = commands.add_parser("ack", help="Acknowledge a directive from an adapter.")
    acknowledge.add_argument("directive_id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = DirectiveStore(args.directives)
    try:
        if args.command == "snapshot":
            value = LiveTelemetryCollector(args.repository).snapshot()
        elif args.command == "inbox":
            value = store.snapshot()
        elif args.command == "ack":
            value = store.mark(args.directive_id, status="acknowledged")
        else:
            value = store.create(
                teammate=args.teammate,
                message=args.message,
                provider=args.provider,
                session_id=args.session_id,
            )
            if args.deliver_now:
                value = DirectiveDispatcher(store, args.repository).dispatch(value)
    except (DirectiveDispatchError, DirectiveStoreError, TelemetryError) as exc:
        print(f"spidey-sense-live: error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(value, indent=2 if args.pretty else None))
    return 0
