"""Cross-reference dependency edges with active teammate file activity."""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Mapping


class BlockerDataError(RuntimeError):
    """Raised when graph or activity input does not match its expected schema."""


def load_dependency_graph(path: str | Path) -> dict[str, object]:
    graph_path = Path(path).expanduser().resolve()
    try:
        data = json.loads(graph_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BlockerDataError(
            f"dependency graph contains invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise BlockerDataError(f"cannot read dependency graph {graph_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BlockerDataError("dependency graph root must be a JSON object")
    return data


def _working_files(activity: Mapping[str, object]) -> dict[str, tuple[str, ...]]:
    if activity.get("schema_version") != "1.0":
        raise BlockerDataError(
            f"unsupported activity schema: {activity.get('schema_version')!r}"
        )
    teammates = activity.get("teammates")
    if not isinstance(teammates, dict):
        raise BlockerDataError("activity 'teammates' must be a JSON object")

    working: dict[str, tuple[str, ...]] = {}
    for teammate, raw_record in teammates.items():
        if not isinstance(teammate, str) or not teammate:
            raise BlockerDataError("activity teammate keys must be non-empty strings")
        if not isinstance(raw_record, dict):
            raise BlockerDataError(f"activity for {teammate!r} must be a JSON object")
        status = raw_record.get("status")
        files = raw_record.get("files")
        if not isinstance(status, str):
            raise BlockerDataError(f"activity status for {teammate!r} must be a string")
        if status not in {"pending", "working", "done"}:
            raise BlockerDataError(f"activity status for {teammate!r} is invalid: {status!r}")
        if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
            raise BlockerDataError(f"activity files for {teammate!r} must be a string array")
        if status == "working":
            working[teammate] = tuple(dict.fromkeys(files))
    return working


def _dependency_edges(graph: Mapping[str, object]) -> list[dict[str, object]]:
    if graph.get("schema_version") != "1.0":
        raise BlockerDataError(f"unsupported dependency graph schema: {graph.get('schema_version')!r}")
    raw_edges = graph.get("edges")
    if not isinstance(raw_edges, list):
        raise BlockerDataError("dependency graph 'edges' must be a JSON array")

    edges: list[dict[str, object]] = []
    for index, raw_edge in enumerate(raw_edges):
        if not isinstance(raw_edge, dict):
            raise BlockerDataError(f"dependency edge {index} must be a JSON object")
        source = raw_edge.get("source")
        target = raw_edge.get("target")
        if not isinstance(source, str) or not source:
            raise BlockerDataError(f"dependency edge {index} has an invalid source")
        if not isinstance(target, str) or not target:
            raise BlockerDataError(f"dependency edge {index} has an invalid target")
        edge: dict[str, object] = {"source": source, "target": target}
        for field in ("kind", "specifier", "line"):
            if field in raw_edge:
                edge[field] = raw_edge[field]
        edges.append(edge)

    return sorted(
        edges,
        key=lambda edge: (
            str(edge["source"]),
            str(edge["target"]),
            int(edge.get("line", 0)) if isinstance(edge.get("line", 0), int) else 0,
        ),
    )


def detect_blockers(
    graph: Mapping[str, object],
    activity: Mapping[str, object],
) -> list[dict[str, object]]:
    """Return deterministic directed blockers for teammates currently working.

    For a dependency edge ``source -> target``, work on ``target`` blocks work on
    ``source``. Same-file conflicts produce one record in each direction because
    neither participant has a natural upstream/downstream role.
    """

    working = _working_files(activity)
    edges = _dependency_edges(graph)
    teammates_by_file: dict[str, list[str]] = {}
    for teammate, files in working.items():
        for file_path in files:
            teammates_by_file.setdefault(file_path, []).append(teammate)
    for teammates in teammates_by_file.values():
        teammates.sort(key=lambda item: (item.casefold(), item))

    blockers: list[dict[str, object]] = []

    for file_path in sorted(teammates_by_file):
        teammates = teammates_by_file[file_path]
        for first, second in combinations(teammates, 2):
            blockers.append(_same_file_blocker(first, second, file_path))
            blockers.append(_same_file_blocker(second, first, file_path))

    for edge in edges:
        blocked_file = str(edge["source"])
        blocking_file = str(edge["target"])
        if blocked_file == blocking_file:
            continue
        for blocking_teammate in teammates_by_file.get(blocking_file, []):
            for blocked_teammate in teammates_by_file.get(blocked_file, []):
                if blocking_teammate == blocked_teammate:
                    continue
                blockers.append(
                    {
                        "blocking_teammate": blocking_teammate,
                        "blocked_teammate": blocked_teammate,
                        "type": "dependency",
                        "blocking_file": blocking_file,
                        "blocked_file": blocked_file,
                        "reciprocal": False,
                        "dependency": edge,
                    }
                )

    unique: dict[tuple[str, str, str, str, str], dict[str, object]] = {}
    for blocker in blockers:
        key = (
            str(blocker["blocking_teammate"]),
            str(blocker["blocked_teammate"]),
            str(blocker["type"]),
            str(blocker["blocking_file"]),
            str(blocker["blocked_file"]),
        )
        unique.setdefault(key, blocker)

    return [
        unique[key]
        for key in sorted(
            unique,
            key=lambda key: (
                key[1].casefold(),
                key[0].casefold(),
                key[2],
                key[4],
                key[3],
            ),
        )
    ]


def _same_file_blocker(
    blocking_teammate: str,
    blocked_teammate: str,
    file_path: str,
) -> dict[str, object]:
    return {
        "blocking_teammate": blocking_teammate,
        "blocked_teammate": blocked_teammate,
        "type": "same_file",
        "blocking_file": file_path,
        "blocked_file": file_path,
        "reciprocal": True,
        "dependency": None,
    }
