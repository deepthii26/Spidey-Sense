from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from spidey_sense.activity import ActivityStore
from spidey_sense.github import (
    GITHUB_API_VERSION,
    CommitActivity,
    GitHubAPIError,
    GitHubClient,
    MergedPullRequest,
    sync_github_activity,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class StubGitHubClient:
    def __init__(self, pulls: list[MergedPullRequest]):
        self.pulls = pulls
        self.calls: list[tuple[str, datetime | None, int]] = []

    def list_merged_pull_requests(
        self,
        repository: str,
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[MergedPullRequest]:
        self.calls.append((repository, since, limit))
        return self.pulls[:limit]


def merged_pull(
    *,
    author: str = "alice",
    merged_at: str = "2026-09-05T11:00:00Z",
    files: tuple[str, ...] = ("src/app.ts",),
) -> MergedPullRequest:
    return MergedPullRequest(
        number=42,
        title="Ship the app",
        author_login=author,
        merged_at=merged_at,
        merge_commit_sha="merge-sha",
        html_url="https://github.com/acme/radar/pull/42",
        files=files,
        commits=(
            CommitActivity(
                sha="commit-sha",
                message=(
                    "Implement app\n\n"
                    "Entire-Checkpoint: 01K9TQ8ZP7X3F5M2WVJ4CNRB6D"
                ),
                author_login=author,
                committed_at="2026-09-05T10:30:00Z",
                entire_checkpoint_ids=("01K9TQ8ZP7X3F5M2WVJ4CNRB6D",),
            ),
        ),
    )


class FakeResponse:
    def __init__(self, payload: object, headers: Message | None = None):
        self.payload = json.dumps(payload).encode("utf-8")
        self.headers = headers or Message()

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class GitHubSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temporary_directory.name) / "activity.json"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_matching_merge_marks_activity_done(self) -> None:
        instants = iter(
            [
                datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
            ]
        )
        store = ActivityStore(self.store_path, clock=lambda: next(instants))
        store.upsert("alice", ["src/app.ts", "src/other.ts"], "working")
        client = StubGitHubClient([merged_pull()])

        result = sync_github_activity(
            client,  # type: ignore[arg-type]
            "acme/radar",
            store,
            clock=lambda: datetime(2026, 9, 5, 12, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(store.get("alice").status, "done")
        self.assertEqual(result["updates"][0]["matched_files"], ["src/app.ts"])
        self.assertEqual(
            result["merged_pull_requests"][0]["commits"][0]["sha"],
            "commit-sha",
        )
        self.assertEqual(
            result["merged_pull_requests"][0]["commits"][0]["entire_checkpoint_ids"],
            ["01K9TQ8ZP7X3F5M2WVJ4CNRB6D"],
        )

    def test_old_or_unrelated_merges_do_not_complete_new_work(self) -> None:
        instant = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
        store = ActivityStore(self.store_path, clock=lambda: instant)
        store.upsert("alice", ["src/new.ts"], "working")
        pulls = [
            merged_pull(merged_at="2026-09-05T11:00:00Z", files=("src/new.ts",)),
            merged_pull(author="bob", merged_at="2026-09-05T13:00:00Z", files=("src/new.ts",)),
            merged_pull(merged_at="2026-09-05T13:00:00Z", files=("src/other.ts",)),
        ]

        result = sync_github_activity(
            StubGitHubClient(pulls),  # type: ignore[arg-type]
            "acme/radar",
            store,
        )

        self.assertEqual(result["updates"], [])
        self.assertEqual(store.get("alice").status, "working")

    def test_identity_map_connects_github_login_to_teammate(self) -> None:
        instants = iter(
            [
                datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
            ]
        )
        store = ActivityStore(self.store_path, clock=lambda: next(instants))
        store.upsert("Alice Smith", ["src/app.ts"], "pending")

        result = sync_github_activity(
            StubGitHubClient([merged_pull(author="alice-gh")]),  # type: ignore[arg-type]
            "acme/radar",
            store,
            identity_map={"ALICE-GH": "Alice Smith"},
        )

        self.assertEqual(result["updates"][0]["teammate"], "Alice Smith")
        self.assertEqual(store.get("Alice Smith").status, "done")


class GitHubClientTests(unittest.TestCase):
    def test_client_follows_pagination_and_sends_required_headers(self) -> None:
        requests = []

        def opener(request: object, timeout: float) -> FakeResponse:
            requests.append((request, timeout))
            url = request.full_url  # type: ignore[attr-defined]
            parsed = urlsplit(url)
            query = parse_qs(parsed.query)
            headers = Message()
            if parsed.path.endswith("/pulls"):
                return FakeResponse(
                    [
                        {
                            "number": 7,
                            "title": "Merged work",
                            "user": {"login": "alice"},
                            "merged_at": "2026-09-05T11:00:00Z",
                            "merge_commit_sha": "merge-sha",
                            "html_url": "https://github.com/acme/radar/pull/7",
                        }
                    ]
                )
            if parsed.path.endswith("/files") and query.get("page") != ["2"]:
                headers["Link"] = (
                    '<https://api.github.test/repos/acme/radar/pulls/7/files?per_page=100&page=2>; '
                    'rel="next"'
                )
                return FakeResponse([{"filename": "src/app.ts"}], headers)
            if parsed.path.endswith("/files"):
                return FakeResponse([{"filename": "src/core.ts"}])
            if parsed.path.endswith("/commits"):
                return FakeResponse(
                    [
                        {
                            "sha": "commit-sha",
                            "author": {"login": "alice"},
                            "commit": {
                                "message": (
                                    "Ship it\n\n"
                                    "Entire-Checkpoint: 01K9TQ8ZP7X3F5M2WVJ4CNRB6D"
                                ),
                                "committer": {"date": "2026-09-05T10:30:00Z"},
                            },
                        }
                    ]
                )
            raise AssertionError(url)

        client = GitHubClient("secret-token", api_url="https://api.github.test", opener=opener)

        pulls = client.list_merged_pull_requests("acme/radar")

        self.assertEqual(pulls[0].files, ("src/app.ts", "src/core.ts"))
        self.assertEqual(pulls[0].commits[0].sha, "commit-sha")
        self.assertEqual(
            pulls[0].commits[0].entire_checkpoint_ids,
            ("01K9TQ8ZP7X3F5M2WVJ4CNRB6D",),
        )
        first_request = requests[0][0]
        self.assertEqual(first_request.get_header("Authorization"), "Bearer secret-token")
        self.assertEqual(first_request.get_header("X-github-api-version"), GITHUB_API_VERSION)
        self.assertEqual(first_request.get_header("Accept"), "application/vnd.github+json")

    def test_client_retries_transient_server_errors(self) -> None:
        attempts = 0
        waits: list[float] = []

        def opener(request: object, timeout: float) -> FakeResponse:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise HTTPError(
                    request.full_url,  # type: ignore[attr-defined]
                    503,
                    "Service unavailable",
                    Message(),
                    io.BytesIO(b'{"message":"try again"}'),
                )
            return FakeResponse([])

        client = GitHubClient(
            "token",
            api_url="https://api.github.test",
            opener=opener,
            sleep=waits.append,
            jitter=lambda: 0.0,
        )

        self.assertEqual(client.list_merged_pull_requests("acme/radar"), [])
        self.assertEqual(attempts, 2)
        self.assertEqual(waits, [1.0])

    def test_client_honors_secondary_rate_limit_backoff(self) -> None:
        attempts = 0
        waits: list[float] = []

        def opener(request: object, timeout: float) -> FakeResponse:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise HTTPError(
                    request.full_url,  # type: ignore[attr-defined]
                    403,
                    "Forbidden",
                    Message(),
                    io.BytesIO(b'{"message":"secondary rate limit exceeded"}'),
                )
            return FakeResponse([])

        client = GitHubClient(
            "token",
            api_url="https://api.github.test",
            opener=opener,
            sleep=waits.append,
        )

        self.assertEqual(client.list_merged_pull_requests("acme/radar"), [])
        self.assertEqual(waits, [60.0])

    def test_client_rejects_cross_origin_pagination(self) -> None:
        def opener(request: object, timeout: float) -> FakeResponse:
            headers = Message()
            headers["Link"] = '<https://evil.test/steal?page=2>; rel="next"'
            return FakeResponse([], headers)

        client = GitHubClient("token", api_url="https://api.github.test", opener=opener)

        with self.assertRaisesRegex(GitHubAPIError, "refusing to send token"):
            client.list_merged_pull_requests("acme/radar")


class GitHubCLIHandler(BaseHTTPRequestHandler):
    seen_authorization: list[str | None] = []
    seen_api_versions: list[str | None] = []

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        self.__class__.seen_authorization.append(self.headers.get("Authorization"))
        self.__class__.seen_api_versions.append(self.headers.get("X-GitHub-Api-Version"))
        path = urlsplit(self.path).path
        if path.endswith("/pulls"):
            payload: object = [
                {
                    "number": 9,
                    "title": "Complete tracked work",
                    "user": {"login": "alice"},
                    "merged_at": "2026-09-05T11:00:00Z",
                    "merge_commit_sha": "merge-9",
                    "html_url": "https://github.com/acme/radar/pull/9",
                }
            ]
        elif path.endswith("/files"):
            payload = [{"filename": "src/app.ts"}]
        elif path.endswith("/commits"):
            payload = [
                {
                    "sha": "commit-9",
                    "author": {"login": "alice"},
                    "commit": {
                        "message": (
                            "Finish tracked work\n\n"
                            "Entire-Checkpoint: a3b2c4d5e6f7"
                        ),
                        "committer": {"date": "2026-09-05T10:30:00Z"},
                    },
                }
            ]
        else:
            self.send_error(404)
            return
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return None


class GitHubCLIIntegrationTests(unittest.TestCase):
    def test_cli_fetches_merge_and_updates_activity_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store_path = root / "activity.json"
            output_path = root / "sync.json"
            ActivityStore(
                store_path,
                clock=lambda: datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc),
            ).upsert("alice", ["src/app.ts"], "working")
            GitHubCLIHandler.seen_authorization = []
            GitHubCLIHandler.seen_api_versions = []
            server = ThreadingHTTPServer(("127.0.0.1", 0), GitHubCLIHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            api_url = f"http://127.0.0.1:{server.server_port}"
            environment = os.environ.copy()
            environment["BLOCKER_RADAR_TEST_GITHUB_TOKEN"] = "test-token"
            try:
                process = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "spidey_sense.github",
                        "--repo",
                        "acme/radar",
                        "--activity",
                        str(store_path),
                        "--token-env",
                        "BLOCKER_RADAR_TEST_GITHUB_TOKEN",
                        "--api-url",
                        api_url,
                        "--output",
                        str(output_path),
                        "--pretty",
                    ],
                    cwd=PROJECT_ROOT,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["updates"][0]["teammate"], "alice")
            self.assertEqual(result["merged_pull_requests"][0]["commits"][0]["sha"], "commit-9")
            self.assertEqual(
                result["merged_pull_requests"][0]["commits"][0]["entire_checkpoint_ids"],
                ["a3b2c4d5e6f7"],
            )
            self.assertEqual(ActivityStore(store_path).get("alice").status, "done")
            self.assertEqual(GitHubCLIHandler.seen_authorization, ["Bearer test-token"] * 3)
            self.assertEqual(GitHubCLIHandler.seen_api_versions, [GITHUB_API_VERSION] * 3)

    def test_cli_requires_token_environment_variable(self) -> None:
        environment = os.environ.copy()
        environment.pop("BLOCKER_RADAR_MISSING_TOKEN", None)
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "spidey_sense.github",
                "--repo",
                "acme/radar",
                "--token-env",
                "BLOCKER_RADAR_MISSING_TOKEN",
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(process.returncode, 2)
        self.assertIn("is not set", process.stderr)


if __name__ == "__main__":
    unittest.main()
