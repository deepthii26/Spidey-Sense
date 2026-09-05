"""Serve an aggregated Spidey Sense snapshot and the React production build."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Sequence
from urllib.parse import urlsplit

from spidey_sense.activity import ActivityStore, ActivityStoreError
from spidey_sense.blockers import BlockerDataError, detect_blockers
from spidey_sense.graph import GraphBuildError, build_dependency_graph, find_git_root


class DashboardServerError(RuntimeError):
    """Raised for invalid dashboard files or server configuration."""


def _utc_timestamp(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise DashboardServerError("dashboard clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _load_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DashboardServerError(
            f"{label} contains invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise DashboardServerError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DashboardServerError(f"{label} root must be a JSON object")
    return value


class DashboardService:
    """Compose the four backend phase outputs into one frontend payload."""

    def __init__(
        self,
        repository: str | Path,
        *,
        activity_path: str | Path = ".spidey-sense/activity.json",
        graph_path: str | Path | None = None,
        github_sync_path: str | Path | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = find_git_root(repository)
        self.activity_store = ActivityStore(activity_path)
        self.graph_path = Path(graph_path).expanduser().resolve() if graph_path else None
        self.github_sync_path = (
            Path(github_sync_path).expanduser().resolve() if github_sync_path else None
        )
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def snapshot(self) -> dict[str, object]:
        graph = (
            _load_json_object(self.graph_path, "dependency graph")
            if self.graph_path
            else build_dependency_graph(self.repository)
        )
        activity = self.activity_store.snapshot()
        blockers = detect_blockers(graph, activity)
        github_sync = None
        if self.github_sync_path is not None and self.github_sync_path.exists():
            github_sync = _load_json_object(self.github_sync_path, "GitHub sync result")

        return {
            "schema_version": "1.0",
            "generated_at": _utc_timestamp(self.clock),
            "repository": str(self.repository),
            "graph": graph,
            "activity": activity,
            "blockers": blockers,
            "github_sync": github_sync,
        }


def _handler_factory(
    service: DashboardService,
    static_directory: Path,
) -> type[SimpleHTTPRequestHandler]:
    class DashboardRequestHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(static_directory), **kwargs)

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler method name.
            route = urlsplit(self.path).path
            if route == "/api/dashboard":
                self._dashboard_response()
                return
            if route == "/api/health":
                self._json_response(HTTPStatus.OK, {"status": "ok"})
                return
            super().do_GET()

        def do_HEAD(self) -> None:  # noqa: N802 - stdlib handler method name.
            route = urlsplit(self.path).path
            if route in {"/api/dashboard", "/api/health"}:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            super().do_HEAD()

        def _dashboard_response(self) -> None:
            try:
                self._json_response(HTTPStatus.OK, service.snapshot())
            except (ActivityStoreError, BlockerDataError, DashboardServerError, GraphBuildError) as exc:
                self._json_response(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": str(exc)},
                )

        def _json_response(self, status: HTTPStatus, value: object) -> None:
            body = (json.dumps(value, separators=(",", ":")) + "\n").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return DashboardRequestHandler


def create_server(
    service: DashboardService,
    static_directory: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    static_path = Path(static_directory).expanduser().resolve()
    if not static_path.is_dir() or not (static_path / "index.html").is_file():
        raise DashboardServerError(
            f"frontend build not found at {static_path}; run 'npm run build' in frontend/"
        )
    return ThreadingHTTPServer((host, port), _handler_factory(service, static_path))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spidey-sense-dashboard",
        description="Serve the Spidey Sense pathway dashboard and local data API.",
    )
    parser.add_argument("--repository", default=".", help="Local git repository to visualize.")
    parser.add_argument(
        "--activity",
        type=Path,
        default=Path(".spidey-sense/activity.json"),
        help="Phase 2 activity JSON.",
    )
    parser.add_argument("--graph", type=Path, help="Optional prebuilt Phase 1 graph JSON.")
    parser.add_argument("--github-sync", type=Path, help="Optional Phase 4 sync-result JSON.")
    parser.add_argument(
        "--frontend",
        type=Path,
        default=Path("frontend/dist"),
        help="Built React directory (default: frontend/dist).",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        service = DashboardService(
            args.repository,
            activity_path=args.activity,
            graph_path=args.graph,
            github_sync_path=args.github_sync,
        )
        server = create_server(service, args.frontend, host=args.host, port=args.port)
    except (DashboardServerError, GraphBuildError, OSError) as exc:
        print(f"spidey-sense-dashboard: error: {exc}", file=sys.stderr)
        return 2

    address, port = server.server_address[:2]
    print(f"Spidey Sense dashboard: http://{address}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
