from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from spidey_sense.activity import ActivityStore
from spidey_sense.blockers import BlockerDataError, detect_blockers


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def graph_with_edges(*edges: dict[str, object]) -> dict[str, object]:
    return {"schema_version": "1.0", "nodes": [], "edges": list(edges)}


def activity_with_teammates(**records: tuple[str, list[str]]) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "teammates": {
            teammate: {
                "teammate": teammate,
                "status": status,
                "files": files,
                "updated_at": "2026-09-05T10:00:00.000000Z",
            }
            for teammate, (status, files) in records.items()
        },
    }


class BlockerDetectionTests(unittest.TestCase):
    def test_dependency_target_blocks_importer(self) -> None:
        graph = graph_with_edges(
            {
                "source": "src/app.ts",
                "target": "src/core.ts",
                "kind": "import",
                "specifier": "./core",
                "line": 1,
            }
        )
        activity = activity_with_teammates(
            alice=("working", ["src/core.ts"]),
            bob=("working", ["src/app.ts"]),
        )

        blockers = detect_blockers(graph, activity)

        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0]["blocking_teammate"], "alice")
        self.assertEqual(blockers[0]["blocked_teammate"], "bob")
        self.assertEqual(blockers[0]["blocking_file"], "src/core.ts")
        self.assertEqual(blockers[0]["blocked_file"], "src/app.ts")
        self.assertEqual(blockers[0]["dependency"]["specifier"], "./core")

    def test_same_file_conflict_is_reciprocal(self) -> None:
        activity = activity_with_teammates(
            alice=("working", ["src/shared.py"]),
            bob=("working", ["src/shared.py"]),
        )

        blockers = detect_blockers(graph_with_edges(), activity)

        directions = {
            (item["blocking_teammate"], item["blocked_teammate"])
            for item in blockers
        }
        self.assertEqual(directions, {("alice", "bob"), ("bob", "alice")})
        self.assertTrue(all(item["type"] == "same_file" for item in blockers))
        self.assertTrue(all(item["reciprocal"] for item in blockers))

    def test_only_working_teammates_participate(self) -> None:
        graph = graph_with_edges({"source": "app.py", "target": "core.py"})
        activity = activity_with_teammates(
            alice=("done", ["core.py"]),
            bob=("working", ["app.py"]),
            carol=("pending", ["app.py"]),
        )

        self.assertEqual(detect_blockers(graph, activity), [])

    def test_multiple_files_and_duplicate_edges_are_deduplicated(self) -> None:
        edge = {"source": "app.py", "target": "core.py", "kind": "import", "line": 1}
        graph = graph_with_edges(edge, {**edge, "line": 2})
        activity = activity_with_teammates(
            alice=("working", ["core.py", "utils.py"]),
            bob=("working", ["app.py"]),
        )

        blockers = detect_blockers(graph, activity)

        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0]["dependency"]["line"], 1)

    def test_teammate_does_not_block_themselves(self) -> None:
        graph = graph_with_edges({"source": "app.py", "target": "core.py"})
        activity = activity_with_teammates(alice=("working", ["app.py", "core.py"]))

        self.assertEqual(detect_blockers(graph, activity), [])

    def test_invalid_schemas_are_rejected(self) -> None:
        with self.assertRaises(BlockerDataError):
            detect_blockers({"schema_version": "2.0", "edges": []}, activity_with_teammates())
        with self.assertRaises(BlockerDataError):
            detect_blockers(graph_with_edges(), {"schema_version": "1.0", "teammates": []})
        with self.assertRaises(BlockerDataError):
            detect_blockers(
                graph_with_edges(),
                activity_with_teammates(alice=("blocked", ["app.py"])),
            )

    def test_cli_outputs_a_plain_json_list(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_path = root / "graph.json"
            activity_path = root / "activity.json"
            graph_path.write_text(
                json.dumps(graph_with_edges({"source": "app.py", "target": "core.py"})),
                encoding="utf-8",
            )
            store = ActivityStore(activity_path)
            store.upsert("alice", ["core.py"], "working")
            store.upsert("bob", ["app.py"], "working")

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "spidey_sense.blockers",
                    "--graph",
                    str(graph_path),
                    "--activity",
                    str(activity_path),
                    "--pretty",
                ],
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        blockers = json.loads(process.stdout)
        self.assertIsInstance(blockers, list)
        self.assertEqual(blockers[0]["blocking_teammate"], "alice")
        self.assertEqual(blockers[0]["blocked_teammate"], "bob")


if __name__ == "__main__":
    unittest.main()
