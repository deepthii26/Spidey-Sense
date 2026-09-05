from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from spidey_sense.activity import ActivityStore
from spidey_sense.dashboard import DashboardService, DashboardServerError, create_server


class DashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "app.py").write_text("import core\n", encoding="utf-8")
        (self.root / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.activity_path = self.root / ".state" / "activity.json"
        instant = datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)
        store = ActivityStore(self.activity_path, clock=lambda: instant)
        store.upsert("alice", ["core.py"], "working")
        store.upsert("bob", ["app.py"], "working")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_service_combines_graph_activity_and_blockers(self) -> None:
        generated = datetime(2026, 9, 5, 10, 5, tzinfo=timezone.utc)
        service = DashboardService(
            self.root,
            activity_path=self.activity_path,
            clock=lambda: generated,
        )

        payload = service.snapshot()

        self.assertEqual(payload["generated_at"], "2026-09-05T10:05:00.000000Z")
        self.assertEqual(payload["graph"]["stats"]["nodes"], 2)
        self.assertEqual(payload["activity"]["teammates"]["alice"]["status"], "working")
        self.assertEqual(payload["blockers"][0]["blocking_teammate"], "alice")
        self.assertEqual(payload["blockers"][0]["blocked_teammate"], "bob")

    def test_server_exposes_api_and_static_frontend(self) -> None:
        static_directory = self.root / "dist"
        static_directory.mkdir()
        (static_directory / "index.html").write_text("<h1>Spidey Sense</h1>", encoding="utf-8")
        service = DashboardService(self.root, activity_path=self.activity_path)
        server = create_server(service, static_directory, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(f"{base_url}/api/dashboard", timeout=5) as response:
                payload = json.loads(response.read())
                self.assertEqual(response.headers["Cache-Control"], "no-store")
            with urlopen(base_url, timeout=5) as response:
                html = response.read().decode("utf-8")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(payload["schema_version"], "1.0")
        self.assertIn("Spidey Sense", html)

    def test_server_requires_a_built_frontend(self) -> None:
        service = DashboardService(self.root, activity_path=self.activity_path)
        with self.assertRaisesRegex(DashboardServerError, "frontend build not found"):
            create_server(service, self.root / "missing", port=0)


if __name__ == "__main__":
    unittest.main()
