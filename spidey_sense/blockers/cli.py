"""Command-line interface for Phase 3 blocker detection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from spidey_sense.activity import ActivityStore, ActivityStoreError

from .detector import BlockerDataError, detect_blockers, load_dependency_graph


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spidey-sense-blockers",
        description="Detect blockers by combining a dependency graph with active teammate work.",
    )
    parser.add_argument("--graph", type=Path, required=True, help="Phase 1 dependency graph JSON.")
    parser.add_argument(
        "--activity",
        type=Path,
        default=Path(".spidey-sense/activity.json"),
        help="Phase 2 activity JSON (default: .spidey-sense/activity.json).",
    )
    parser.add_argument("-o", "--output", type=Path, help="Write the blocker list to a file.")
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        graph = load_dependency_graph(args.graph)
        activity = ActivityStore(args.activity).snapshot()
        blockers = detect_blockers(graph, activity)
        payload = json.dumps(
            blockers,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        ) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
    except (ActivityStoreError, BlockerDataError) as exc:
        print(f"spidey-sense-blockers: error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"spidey-sense-blockers: error: cannot write output: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
