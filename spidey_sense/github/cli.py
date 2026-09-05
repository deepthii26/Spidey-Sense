"""Command-line interface for synchronizing GitHub merges into activity."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from spidey_sense.activity import ActivityStore, ActivityStoreError

from .client import GitHubAPIError, GitHubClient, parse_github_timestamp
from .sync import GitHubSyncError, load_identity_map, sync_github_activity


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spidey-sense-github",
        description="Synchronize merged GitHub pull requests with teammate activity.",
    )
    parser.add_argument("--repo", required=True, help="GitHub repository in owner/name format.")
    parser.add_argument(
        "--activity",
        type=Path,
        default=Path(".spidey-sense/activity.json"),
        help="Phase 2 activity JSON (default: .spidey-sense/activity.json).",
    )
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="Environment variable containing the token (default: GITHUB_TOKEN).",
    )
    parser.add_argument(
        "--identity-map",
        type=Path,
        help="Optional JSON object mapping GitHub logins to teammate names.",
    )
    parser.add_argument("--since", help="Only inspect merges at or after this ISO-8601 timestamp.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum merged PRs to inspect.")
    parser.add_argument(
        "--api-url",
        default="https://api.github.com",
        help="GitHub API base URL, including an Enterprise API URL when needed.",
    )
    parser.add_argument("-o", "--output", type=Path, help="Write sync details to this JSON file.")
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    token = os.environ.get(args.token_env)
    if not token:
        print(
            f"spidey-sense-github: error: environment variable {args.token_env} is not set",
            file=sys.stderr,
        )
        return 2

    try:
        since: datetime | None = None
        if args.since:
            since = parse_github_timestamp(args.since, field="--since")
        identity_map = load_identity_map(args.identity_map) if args.identity_map else None
        client = GitHubClient(token, api_url=args.api_url)
        result = sync_github_activity(
            client,
            args.repo,
            ActivityStore(args.activity),
            identity_map=identity_map,
            since=since,
            limit=args.limit,
        )
        payload = json.dumps(
            result,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        ) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
    except (ActivityStoreError, GitHubAPIError, GitHubSyncError) as exc:
        print(f"spidey-sense-github: error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"spidey-sense-github: error: cannot write output: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
