"""Small dependency-free client for the GitHub pull request REST API."""

from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
from typing import Callable, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen


GITHUB_API_VERSION = "2026-03-10"
RETRIABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')
_ENTIRE_CHECKPOINT_TRAILER = re.compile(
    r"^Entire-Checkpoint:[ \t]*"
    r"([0-9A-HJKMNP-TV-Z]{26}|[0-9A-F]{12})[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


class GitHubAPIError(RuntimeError):
    """Raised for GitHub transport, authentication, or response errors."""


def parse_github_timestamp(value: str, *, field: str = "timestamp") -> datetime:
    if not isinstance(value, str) or not value:
        raise GitHubAPIError(f"GitHub {field} is missing or invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GitHubAPIError(f"GitHub {field} is not a valid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GitHubAPIError(f"GitHub {field} must include a timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def normalise_repository(repository: str) -> tuple[str, str]:
    value = repository.strip()
    parts = value.split("/")
    if len(parts) != 2 or not all(parts):
        raise GitHubAPIError("repository must use the owner/name format")
    owner, name = parts
    if name.endswith(".git"):
        name = name[:-4]
    if not name:
        raise GitHubAPIError("repository name must not be empty")
    return owner, name


@dataclass(frozen=True)
class CommitActivity:
    sha: str
    message: str
    author_login: str | None
    committed_at: str | None
    entire_checkpoint_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "sha": self.sha,
            "message": self.message,
            "author_login": self.author_login,
            "committed_at": self.committed_at,
            "entire_checkpoint_ids": list(self.entire_checkpoint_ids),
        }


@dataclass(frozen=True)
class MergedPullRequest:
    number: int
    title: str
    author_login: str
    merged_at: str
    merge_commit_sha: str | None
    html_url: str
    files: tuple[str, ...]
    commits: tuple[CommitActivity, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "number": self.number,
            "title": self.title,
            "author_login": self.author_login,
            "merged_at": self.merged_at,
            "merge_commit_sha": self.merge_commit_sha,
            "html_url": self.html_url,
            "files": list(self.files),
            "commits": [commit.to_dict() for commit in self.commits],
        }


class GitHubClient:
    """Read merged pull requests, changed files, and commits serially."""

    def __init__(
        self,
        token: str,
        *,
        api_url: str = "https://api.github.com",
        timeout: float = 20.0,
        max_retries: int = 3,
        max_retry_delay: float = 60.0,
        opener: Callable[..., object] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        if not token.strip():
            raise GitHubAPIError("GitHub token must not be empty")
        if max_retries < 0:
            raise GitHubAPIError("max_retries must not be negative")
        self.token = token.strip()
        self.api_url = api_url.rstrip("/")
        parsed_api_url = urlsplit(self.api_url)
        if parsed_api_url.scheme not in {"http", "https"} or not parsed_api_url.netloc:
            raise GitHubAPIError(f"invalid GitHub API URL: {api_url}")
        self._api_origin = (parsed_api_url.scheme, parsed_api_url.netloc)
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_retry_delay = max_retry_delay
        self._opener = opener or urlopen
        self._sleep = sleep
        self._now = now
        self._jitter = jitter

    def list_merged_pull_requests(
        self,
        repository: str,
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[MergedPullRequest]:
        if limit < 1:
            raise GitHubAPIError("pull request limit must be at least 1")
        if since is not None:
            if since.tzinfo is None or since.utcoffset() is None:
                raise GitHubAPIError("since must include a timezone")
            since = since.astimezone(timezone.utc)

        owner, name = normalise_repository(repository)
        repository_path = f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
        query = urlencode(
            {
                "state": "closed",
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
            }
        )
        first_url = f"{self.api_url}{repository_path}/pulls?{query}"
        merged: list[MergedPullRequest] = []

        for raw_pull in self._iter_paginated(first_url):
            merged_at = raw_pull.get("merged_at")
            if merged_at is None:
                continue
            if not isinstance(merged_at, str):
                raise GitHubAPIError("GitHub pull request merged_at must be a string or null")
            merged_datetime = parse_github_timestamp(merged_at, field="merged_at")
            if since is not None and merged_datetime < since:
                continue

            number = raw_pull.get("number")
            title = raw_pull.get("title")
            user = raw_pull.get("user")
            author_login = user.get("login") if isinstance(user, dict) else None
            html_url = raw_pull.get("html_url")
            merge_commit_sha = raw_pull.get("merge_commit_sha")
            if not isinstance(number, int) or number < 1:
                raise GitHubAPIError("GitHub pull request number is missing or invalid")
            if not isinstance(title, str):
                raise GitHubAPIError(f"GitHub pull request #{number} title is invalid")
            if not isinstance(author_login, str) or not author_login:
                raise GitHubAPIError(f"GitHub pull request #{number} author is invalid")
            if not isinstance(html_url, str):
                raise GitHubAPIError(f"GitHub pull request #{number} html_url is invalid")
            if merge_commit_sha is not None and not isinstance(merge_commit_sha, str):
                raise GitHubAPIError(f"GitHub pull request #{number} merge_commit_sha is invalid")

            files = self._list_pull_files(repository_path, number)
            commits = self._list_pull_commits(repository_path, number)
            merged.append(
                MergedPullRequest(
                    number=number,
                    title=title,
                    author_login=author_login,
                    merged_at=merged_at,
                    merge_commit_sha=merge_commit_sha,
                    html_url=html_url,
                    files=files,
                    commits=commits,
                )
            )
            if len(merged) >= limit:
                break
        return merged

    def _list_pull_files(self, repository_path: str, number: int) -> tuple[str, ...]:
        url = f"{self.api_url}{repository_path}/pulls/{number}/files?per_page=100"
        files: list[str] = []
        for item in self._iter_paginated(url):
            filename = item.get("filename")
            if not isinstance(filename, str) or not filename:
                raise GitHubAPIError(f"GitHub pull request #{number} returned an invalid filename")
            files.append(filename)
        return tuple(dict.fromkeys(files))

    def _list_pull_commits(
        self,
        repository_path: str,
        number: int,
    ) -> tuple[CommitActivity, ...]:
        url = f"{self.api_url}{repository_path}/pulls/{number}/commits?per_page=100"
        commits: list[CommitActivity] = []
        for item in self._iter_paginated(url):
            sha = item.get("sha")
            commit = item.get("commit")
            author = item.get("author")
            author_login = author.get("login") if isinstance(author, dict) else None
            if not isinstance(sha, str) or not sha:
                raise GitHubAPIError(f"GitHub pull request #{number} returned an invalid commit SHA")
            if not isinstance(commit, dict):
                raise GitHubAPIError(f"GitHub pull request #{number} returned invalid commit data")
            message = commit.get("message")
            committer = commit.get("committer")
            committed_at = committer.get("date") if isinstance(committer, dict) else None
            if not isinstance(message, str):
                raise GitHubAPIError(f"GitHub commit {sha} has an invalid message")
            if author_login is not None and not isinstance(author_login, str):
                author_login = None
            if committed_at is not None and not isinstance(committed_at, str):
                committed_at = None
            checkpoint_ids = tuple(
                dict.fromkeys(match.group(1) for match in _ENTIRE_CHECKPOINT_TRAILER.finditer(message))
            )
            commits.append(
                CommitActivity(sha, message, author_login, committed_at, checkpoint_ids)
            )
        return tuple(commits)

    def _iter_paginated(self, first_url: str) -> Iterator[dict[str, object]]:
        next_url: str | None = first_url
        while next_url:
            payload, headers = self._request_json(next_url)
            if not isinstance(payload, list):
                raise GitHubAPIError("GitHub paginated response must be a JSON array")
            for item in payload:
                if not isinstance(item, dict):
                    raise GitHubAPIError("GitHub paginated response contained a non-object item")
                yield item
            next_url = self._next_url(headers)

    def _request_json(self, url: str) -> tuple[object, Message | object]:
        self._validate_request_url(url)
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
                "User-Agent": "spidey-sense/0.6.0",
            },
            method="GET",
        )

        for attempt in range(self.max_retries + 1):
            try:
                response = self._opener(request, timeout=self.timeout)
                with response:  # type: ignore[attr-defined]
                    raw_body = response.read()  # type: ignore[attr-defined]
                    headers = response.headers  # type: ignore[attr-defined]
                try:
                    return json.loads(raw_body.decode("utf-8")), headers
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise GitHubAPIError(f"GitHub returned invalid JSON for {url}") from exc
            except HTTPError as exc:
                try:
                    body = exc.read().decode("utf-8", errors="replace")
                    headers = exc.headers
                finally:
                    exc.close()
                message = self._error_message(body)
                rate_limited = self._is_rate_limited(exc.code, headers, message)
                should_retry = exc.code in RETRIABLE_STATUS_CODES or rate_limited
                if not should_retry or attempt >= self.max_retries:
                    raise GitHubAPIError(
                        f"GitHub API request failed with HTTP {exc.code}: {message}"
                    ) from exc
                self._wait_before_retry(attempt, headers, rate_limited=rate_limited)
            except URLError as exc:
                if attempt >= self.max_retries:
                    raise GitHubAPIError(f"GitHub API request failed: {exc.reason}") from exc
                self._wait_before_retry(attempt, None)
        raise AssertionError("retry loop exited unexpectedly")

    def _validate_request_url(self, url: str) -> None:
        parsed = urlsplit(url)
        if (parsed.scheme, parsed.netloc) != self._api_origin:
            raise GitHubAPIError("GitHub pagination URL changed API origin; refusing to send token")

    @staticmethod
    def _error_message(body: str) -> str:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return body.strip() or "unknown error"
        if isinstance(payload, dict) and isinstance(payload.get("message"), str):
            return payload["message"]
        return "unknown error"

    @staticmethod
    def _is_rate_limited(status: int, headers: Message, message: str) -> bool:
        if status not in {403, 429}:
            return False
        return (
            headers.get("Retry-After") is not None
            or headers.get("X-RateLimit-Remaining") == "0"
            or "rate limit" in message.casefold()
        )

    def _wait_before_retry(
        self,
        attempt: int,
        headers: Message | None,
        *,
        rate_limited: bool = False,
    ) -> None:
        delay: float
        retry_after = headers.get("Retry-After") if headers is not None else None
        remaining = headers.get("X-RateLimit-Remaining") if headers is not None else None
        reset = headers.get("X-RateLimit-Reset") if headers is not None else None
        if retry_after is not None:
            try:
                delay = max(0.0, float(retry_after))
            except ValueError:
                delay = 60.0
        elif remaining == "0" and reset is not None:
            try:
                delay = max(0.0, float(reset) - self._now())
            except ValueError:
                delay = 60.0
        elif rate_limited:
            delay = 60.0
        else:
            delay = min(2.0**attempt, self.max_retry_delay) + min(self._jitter(), 1.0)
        if delay > self.max_retry_delay:
            raise GitHubAPIError(
                f"GitHub requested a {delay:.0f}s retry delay, exceeding the configured maximum"
            )
        self._sleep(delay)

    @staticmethod
    def _next_url(headers: Message | object) -> str | None:
        link = headers.get("Link")  # type: ignore[attr-defined]
        if not isinstance(link, str):
            return None
        match = _NEXT_LINK.search(link)
        return match.group(1) if match else None
