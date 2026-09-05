"""Apply GitHub merge activity to the local teammate activity store."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from spidey_sense.activity import ActivityRecord, ActivityStore, ActivityStoreError

from .client import GitHubClient, parse_github_timestamp


class GitHubSyncError(RuntimeError):
    """Raised when identity or timestamp data cannot be synchronized safely."""


def load_identity_map(path: str | Path) -> dict[str, str]:
    identity_path = Path(path).expanduser().resolve()
    try:
        data = json.loads(identity_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GitHubSyncError(
            f"identity map contains invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise GitHubSyncError(f"cannot read identity map {identity_path}: {exc}") from exc
    if not isinstance(data, dict) or not all(
        isinstance(login, str) and login and isinstance(teammate, str) and teammate
        for login, teammate in data.items()
    ):
        raise GitHubSyncError("identity map must be a JSON object of GitHub login to teammate name")
    return {login.casefold(): teammate for login, teammate in data.items()}


def _parse_activity_timestamp(value: str, teammate: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GitHubSyncError(
            f"activity timestamp for {teammate!r} is not valid ISO-8601: {value!r}"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GitHubSyncError(f"activity timestamp for {teammate!r} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _format_now(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise GitHubSyncError("sync clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def sync_github_activity(
    client: GitHubClient,
    repository: str,
    store: ActivityStore,
    *,
    identity_map: Mapping[str, str] | None = None,
    since: datetime | None = None,
    limit: int = 100,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Fetch recent merges and mark matching current teammate work as done."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    snapshot = store.snapshot()
    raw_teammates = snapshot.get("teammates")
    if not isinstance(raw_teammates, dict):
        raise GitHubSyncError("activity snapshot has an invalid teammates object")

    records: dict[str, ActivityRecord] = {}
    for teammate, raw_record in raw_teammates.items():
        if not isinstance(teammate, str):
            raise GitHubSyncError("activity teammate keys must be strings")
        try:
            records[teammate] = ActivityRecord.from_dict(teammate, raw_record)
        except ActivityStoreError as exc:
            raise GitHubSyncError(str(exc)) from exc

    by_casefold = {teammate.casefold(): teammate for teammate in records}
    mapped_identities: dict[str, str] = {}
    for login, teammate in (identity_map or {}).items():
        if not isinstance(login, str) or not login or not isinstance(teammate, str) or not teammate:
            raise GitHubSyncError("identity map entries must contain non-empty string names")
        mapped_identities[login.casefold()] = teammate
    pulls = client.list_merged_pull_requests(repository, since=since, limit=limit)
    updates: list[dict[str, object]] = []
    stale_updates: list[dict[str, object]] = []
    completed_teammates: set[str] = set()

    for pull in pulls:
        mapped_teammate = mapped_identities.get(pull.author_login.casefold(), pull.author_login)
        teammate = by_casefold.get(mapped_teammate.casefold())
        if teammate is None or teammate in completed_teammates:
            continue
        record = records[teammate]
        if record.status == "done":
            continue
        merged_at = parse_github_timestamp(pull.merged_at, field="merged_at")
        if merged_at < _parse_activity_timestamp(record.updated_at, teammate):
            continue
        matched_files = sorted(set(record.files).intersection(pull.files))
        if not matched_files:
            continue

        updated = store.update_status_if_current(
            teammate,
            "done",
            expected_updated_at=record.updated_at,
            expected_files=record.files,
        )
        update = {
            "teammate": teammate,
            "previous_status": record.status,
            "status": "done",
            "matched_files": matched_files,
            "pull_request": {
                "number": pull.number,
                "title": pull.title,
                "author_login": pull.author_login,
                "merged_at": pull.merged_at,
                "merge_commit_sha": pull.merge_commit_sha,
                "html_url": pull.html_url,
            },
        }
        if updated is None:
            stale_updates.append({**update, "reason": "activity_changed_during_sync"})
            continue
        updates.append(update)
        completed_teammates.add(teammate)

    return {
        "schema_version": "1.0",
        "repository": repository,
        "checked_at": _format_now(clock),
        "merged_pull_requests": [pull.to_dict() for pull in pulls],
        "updates": updates,
        "skipped_updates": stale_updates,
    }
