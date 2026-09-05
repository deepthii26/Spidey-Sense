"""Command-line interface for the dependency graph engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .graph import GraphBuildError, build_dependency_graph


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spidey-sense",
        description=(
            "Build a JSON file-dependency graph for JavaScript, TypeScript, and "
            "Python files in a local git repository."
        ),
    )
    parser.add_argument(
        "repository",
        nargs="?",
        default=".",
        help="Path to a local git repository (default: current directory).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write JSON to this file instead of stdout.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Indent the JSON output for readability.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        graph = build_dependency_graph(args.repository)
    except GraphBuildError as exc:
        print(f"spidey-sense: error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(
        graph,
        indent=2 if args.pretty else None,
        separators=None if args.pretty else (",", ":"),
        sort_keys=False,
    )
    payload += "\n"

    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        except OSError as exc:
            print(f"spidey-sense: error: cannot write {args.output}: {exc}", file=sys.stderr)
            return 2
    else:
        sys.stdout.write(payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
