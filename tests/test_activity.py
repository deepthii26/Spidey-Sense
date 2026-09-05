from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from spidey_sense.activity import (
    ActivityNotFoundError,
    ActivityStore,
    ActivityStoreError,
    ActivityValidationError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ActivityStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temporary_directory.name) / "state" / "activity.json"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_upsert_persists_normalised_snapshot(self) -> None:
        instant = datetime(2026, 9, 5, 10, 30, tzinfo=timezone.utc)
        store = ActivityStore(self.store_path, clock=lambda: instant)

        record = store.upsert(
            " Alice ",
            ["./src/app.ts", "src\\api.ts", "src/app.ts"],
            "working",
        )

        self.assertEqual(record.teammate, "Alice")
        self.assertEqual(record.files, ("src/app.ts", "src/api.ts"))
        self.assertEqual(record.updated_at, "2026-09-05T10:30:00.000000Z")
        raw = json.loads(self.store_path.read_text(encoding="utf-8"))
        self.assertEqual(raw["schema_version"], "1.0")
        self.assertEqual(raw["teammates"]["Alice"], record.to_dict())

    def test_status_update_retains_files_and_refreshes_timestamp(self) -> None:
        instants = iter(
            [
                datetime(2026, 9, 5, 10, 30, tzinfo=timezone.utc),
                datetime(2026, 9, 5, 10, 45, tzinfo=timezone.utc),
            ]
        )
        store = ActivityStore(self.store_path, clock=lambda: next(instants))
        store.upsert("alice", ["src/app.ts"], "pending")

        record = store.update_status("alice", "working")

        self.assertEqual(record.files, ("src/app.ts",))
        self.assertEqual(record.status, "working")
        self.assertEqual(record.updated_at, "2026-09-05T10:45:00.000000Z")

    def test_remove_and_missing_teammate(self) -> None:
        store = ActivityStore(self.store_path)
        store.upsert("alice", ["app.py"], "done")

        self.assertTrue(store.remove("alice"))
        self.assertFalse(store.remove("alice"))
        with self.assertRaises(ActivityNotFoundError):
            store.get("alice")

    def test_conditional_status_update_rejects_stale_activity(self) -> None:
        store = ActivityStore(self.store_path)
        original = store.upsert("alice", ["old.py"], "working")
        store.upsert("alice", ["new.py"], "working")

        result = store.update_status_if_current(
            "alice",
            "done",
            expected_updated_at=original.updated_at,
            expected_files=original.files,
        )

        self.assertIsNone(result)
        self.assertEqual(store.get("alice").files, ("new.py",))
        self.assertEqual(store.get("alice").status, "working")

    def test_invalid_activity_is_rejected(self) -> None:
        store = ActivityStore(self.store_path)

        with self.assertRaises(ActivityValidationError):
            store.upsert("alice", ["../outside.py"], "working")
        with self.assertRaises(ActivityValidationError):
            store.upsert("alice", [], "working")
        with self.assertRaises(ActivityValidationError):
            store.upsert("alice", ["app.py"], "blocked")

    def test_invalid_json_is_reported(self) -> None:
        self.store_path.parent.mkdir(parents=True)
        self.store_path.write_text("{not-json", encoding="utf-8")

        with self.assertRaisesRegex(ActivityStoreError, "invalid JSON"):
            ActivityStore(self.store_path).snapshot()

    def test_parallel_updates_do_not_lose_teammates(self) -> None:
        def update(index: int) -> None:
            ActivityStore(self.store_path).upsert(
                f"teammate-{index}", [f"src/file-{index}.py"], "working"
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(update, range(20)))

        teammates = ActivityStore(self.store_path).snapshot()["teammates"]
        self.assertEqual(len(teammates), 20)

    def test_cli_lifecycle(self) -> None:
        base_command = [
            sys.executable,
            "-m",
            "spidey_sense.activity",
            "--store",
            str(self.store_path),
        ]

        set_process = subprocess.run(
            [*base_command, "set", "alice", "working", "src/app.ts", "src/api.ts"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(set_process.returncode, 0, set_process.stderr)

        status_process = subprocess.run(
            [*base_command, "status", "alice", "done"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(status_process.returncode, 0, status_process.stderr)
        self.assertEqual(json.loads(status_process.stdout)["status"], "done")

        list_process = subprocess.run(
            [*base_command, "list"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(list_process.returncode, 0, list_process.stderr)
        snapshot = json.loads(list_process.stdout)
        self.assertEqual(snapshot["teammates"]["alice"]["files"], ["src/app.ts", "src/api.ts"])


if __name__ == "__main__":
    unittest.main()
