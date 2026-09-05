from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from spidey_sense.graph import GraphBuildError, build_dependency_graph


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class GitRepository:
    def __init__(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name)
        subprocess.run(["git", "init", "-q", str(self.path)], check=True)

    def write(self, relative: str, content: str) -> None:
        target = self.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def close(self) -> None:
        self.temporary_directory.cleanup()


class DependencyGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = GitRepository()

    def tearDown(self) -> None:
        self.repo.close()

    def test_javascript_and_typescript_dependencies(self) -> None:
        self.repo.write(
            "src/app.ts",
            """import { helper } from './helper.js';
import type { Config } from './types';
export { Button } from './ui';
const lazy = import('./lazy');
const common = require('./common.cjs');
// import ignored from './does-not-exist';
import React from 'react';
""",
        )
        self.repo.write("src/helper.ts", "export const helper = 1;\n")
        self.repo.write("src/types.ts", "export type Config = {};\n")
        self.repo.write("src/ui/index.tsx", "export const Button = () => null;\n")
        self.repo.write("src/lazy.mjs", "export default 1;\n")
        self.repo.write("src/common.cjs", "module.exports = {};\n")

        graph = build_dependency_graph(self.repo.path)

        dependencies = {
            (edge["target"], edge["kind"]) for edge in graph["edges"]
            if edge["source"] == "src/app.ts"
        }
        self.assertEqual(
            dependencies,
            {
                ("src/helper.ts", "import"),
                ("src/types.ts", "import"),
                ("src/ui/index.tsx", "re-export"),
                ("src/lazy.mjs", "dynamic-import"),
                ("src/common.cjs", "require"),
            },
        )
        diagnostic_messages = [item["message"] for item in graph["diagnostics"]]
        self.assertIn("unresolved or external import: react", diagnostic_messages)
        self.assertNotIn("unresolved or external import: ./does-not-exist", diagnostic_messages)

    def test_python_absolute_and_relative_imports(self) -> None:
        self.repo.write("src/acme/__init__.py", "")
        self.repo.write("src/acme/models.py", "class User: pass\n")
        self.repo.write("src/acme/util.py", "VALUE = 1\n")
        self.repo.write(
            "src/acme/service.py",
            """import acme.models
from . import util
from json import loads
""",
        )

        graph = build_dependency_graph(self.repo.path)

        dependencies = {
            edge["target"] for edge in graph["edges"]
            if edge["source"] == "src/acme/service.py"
        }
        self.assertEqual(dependencies, {"src/acme/models.py", "src/acme/util.py"})

    def test_gitignored_files_are_not_scanned(self) -> None:
        self.repo.write(".gitignore", "generated/\n")
        self.repo.write("main.py", "import kept\n")
        self.repo.write("kept.py", "")
        self.repo.write("generated/ignored.py", "")

        graph = build_dependency_graph(self.repo.path)

        paths = {node["path"] for node in graph["nodes"]}
        self.assertEqual(paths, {"main.py", "kept.py"})

    def test_python_syntax_errors_are_diagnostics(self) -> None:
        self.repo.write("broken.py", "def nope(:\n")

        graph = build_dependency_graph(self.repo.path)

        self.assertEqual(graph["stats"]["nodes"], 1)
        self.assertEqual(graph["stats"]["edges"], 0)
        self.assertEqual(graph["diagnostics"][0]["level"], "error")

    def test_cli_outputs_valid_json(self) -> None:
        self.repo.write("app.js", "import './dep.js';\n")
        self.repo.write("dep.js", "")

        process = subprocess.run(
            [sys.executable, "-m", "spidey_sense", str(self.repo.path), "--pretty"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        graph = json.loads(process.stdout)
        self.assertEqual(graph["stats"], {"nodes": 2, "edges": 1, "diagnostics": 0})
        self.assertEqual(graph["edges"][0]["source"], "app.js")
        self.assertEqual(graph["edges"][0]["target"], "dep.js")

    def test_non_git_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(GraphBuildError):
                build_dependency_graph(directory)


if __name__ == "__main__":
    unittest.main()
