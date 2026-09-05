from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from spidey_sense.live.directives import (
    DirectiveDispatchError,
    DirectiveDispatcher,
    DirectiveStore,
    DirectiveStoreError,
)
from spidey_sense.live.telemetry import (
    LiveTelemetryCollector,
    normalise_claude_sessions,
    normalise_codex_threads,
    normalise_entire_sessions,
)


class SessionNormalisationTests(unittest.TestCase):
    def test_codex_threads_are_messageable_and_recent(self) -> None:
        sessions = normalise_codex_threads(
            {
                "data": [
                    {
                        "id": "thread-1",
                        "preview": "Implement the live graph\nwith tests",
                        "recencyAt": 1_000,
                        "status": {"type": "notLoaded"},
                        "modelProvider": "openai",
                    }
                ]
            },
            now=1_100,
        )

        self.assertEqual(sessions[0]["provider"], "codex")
        self.assertEqual(sessions[0]["status"], "recent")
        self.assertTrue(sessions[0]["can_message"])
        self.assertEqual(sessions[0]["summary"], "Implement the live graph with tests")

    def test_claude_and_entire_public_fields_are_normalised(self) -> None:
        claude = normalise_claude_sessions(
            [{"id": "c1", "name": "API agent", "status": "running", "cwd": "/repo"}]
        )
        entire = normalise_entire_sessions(
            [
                {
                    "session_id": "e1",
                    "agent": "Codex",
                    "status": "active",
                    "files_touched": ["src/app.py"],
                    "last_prompt": "Finish the API",
                }
            ]
        )

        self.assertEqual(claude[0]["provider"], "claude")
        self.assertEqual(entire[0]["files"], ["src/app.py"])
        self.assertEqual(entire[0]["summary"], "Finish the API")


class TelemetryCollectorTests(unittest.TestCase):
    def test_git_snapshot_includes_worktree_and_commit_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def runner(command, cwd, timeout):
                del cwd, timeout
                key = tuple(command)
                outputs = {
                    ("git", "branch", "--show-current"): "main\n",
                    ("git", "rev-parse", "HEAD"): "abcdef123456\n",
                    ("git", "remote", "get-url", "origin"): "git@example/repo.git\n",
                    ("git", "status", "--porcelain=v1", "--untracked-files=all"): " M src/app.py\n?? src/new.py\n",
                    ("git", "log", "-8", "--format=%H%x1f%h%x1f%an%x1f%aI%x1f%s"): (
                        "abcdef123456\x1fabcdef1\x1fAlice\x1f2026-09-05T10:00:00Z\x1fShip live view\n"
                    ),
                    (
                        "git",
                        "diff-tree",
                        "--no-commit-id",
                        "--name-only",
                        "-r",
                        "abcdef123456",
                    ): "src/app.py\n",
                }
                return subprocess.CompletedProcess(command, 0, outputs[key], "")

            collector = LiveTelemetryCollector(
                root, runner=runner, which=lambda _command: None
            )
            value = collector.snapshot()

        self.assertEqual(value["git"]["branch"], "main")
        self.assertEqual(value["git"]["dirty_files"][0]["path"], "src/app.py")
        self.assertEqual(value["git"]["commits"][0]["files"], ["src/app.py"])
        self.assertFalse(value["providers"]["codex"]["available"])


class DirectiveTests(unittest.TestCase):
    def test_directive_is_persisted_and_codex_delivery_is_allowlisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = DirectiveStore(root / "directives.json")
            directive = store.create(
                teammate="Alice",
                message="Finish the contract tests",
                provider="codex",
                session_id="thread-1",
            )
            observed = []

            def runner(command, cwd, timeout):
                observed.append((list(command), cwd, timeout))
                return subprocess.CompletedProcess(command, 0, "queued\n", "")

            delivered = DirectiveDispatcher(store, root, runner=runner).dispatch(directive)

            self.assertEqual(delivered["status"], "sent")
            self.assertEqual(observed[0][0][:4], ["codex", "queue", "--thread", "thread-1"])
            self.assertEqual(store.snapshot()["directives"][0]["status"], "sent")

    def test_non_codex_direct_delivery_stays_in_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = DirectiveStore(Path(directory) / "directives.json")
            directive = store.create(
                teammate="Alice", message="Review the API", provider="claude", session_id="c1"
            )
            with self.assertRaisesRegex(DirectiveDispatchError, "only for Codex"):
                DirectiveDispatcher(store, directory).dispatch(directive)
            self.assertEqual(store.snapshot()["directives"][0]["status"], "queued")

    def test_invalid_directive_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = DirectiveStore(Path(directory) / "directives.json")
            with self.assertRaises(DirectiveStoreError):
                store.create(teammate="", message="hello")


if __name__ == "__main__":
    unittest.main()
