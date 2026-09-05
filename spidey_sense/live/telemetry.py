"""Collect local Git and supported coding-agent session telemetry."""

from __future__ import annotations

import json
import selectors
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


class TelemetryError(RuntimeError):
    """Raised when the live telemetry configuration is invalid."""


CommandRunner = Callable[[Sequence[str], Path, float], subprocess.CompletedProcess[str]]


def _default_runner(
    command: Sequence[str], cwd: Path, timeout: float
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def _iso_from_unix(value: object) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def _first(value: dict[str, object], *keys: str) -> object:
    for key in keys:
        if key in value and value[key] not in (None, ""):
            return value[key]
    return None


def _text(value: object, default: str = "") -> str:
    return value.strip() if isinstance(value, str) else default


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def normalise_claude_sessions(value: object) -> list[dict[str, object]]:
    """Normalize the deliberately small public `claude agents --json` surface."""
    if not isinstance(value, list):
        return []
    sessions: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        session_id = _text(_first(item, "id", "session_id", "sessionId"))
        if not session_id:
            continue
        status = _text(_first(item, "status", "state"), "unknown").lower()
        sessions.append(
            {
                "id": session_id,
                "provider": "claude",
                "name": _text(_first(item, "name", "display_name", "displayName"), "Claude Code"),
                "status": status,
                "summary": _text(_first(item, "prompt", "description", "summary", "name"))[:240],
                "updated_at": _text(
                    _first(item, "last_active", "updated_at", "updatedAt", "started_at", "startedAt")
                )
                or None,
                "cwd": _text(_first(item, "cwd", "worktree_path", "worktreePath")) or None,
                "files": _string_list(_first(item, "files", "files_touched", "filesTouched")),
                "model": _text(_first(item, "model")) or None,
                "can_message": False,
            }
        )
    return sessions


def normalise_entire_sessions(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    sessions: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        session_id = _text(_first(item, "session_id", "sessionId", "id"))
        if not session_id:
            continue
        agent = _text(_first(item, "agent"), "AI agent")
        sessions.append(
            {
                "id": session_id,
                "provider": "entire",
                "name": agent,
                "status": _text(_first(item, "status"), "unknown").lower(),
                "summary": _text(_first(item, "last_prompt", "summary"))[:240],
                "updated_at": _text(_first(item, "last_active", "updated_at")) or None,
                "cwd": _text(_first(item, "worktree_path", "cwd")) or None,
                "files": _string_list(_first(item, "files_touched", "files")),
                "model": _text(_first(item, "model")) or None,
                "can_message": False,
            }
        )
    return sessions


def normalise_codex_threads(value: object, *, now: float | None = None) -> list[dict[str, object]]:
    if not isinstance(value, dict) or not isinstance(value.get("data"), list):
        return []
    current_time = now if now is not None else time.time()
    sessions: list[dict[str, object]] = []
    for item in value["data"]:
        if not isinstance(item, dict):
            continue
        session_id = _text(_first(item, "id", "sessionId"))
        if not session_id:
            continue
        updated = _first(item, "recencyAt", "updatedAt")
        status_value = item.get("status")
        status = (
            _text(status_value.get("type"), "unknown")
            if isinstance(status_value, dict)
            else _text(status_value, "unknown")
        )
        if status == "notLoaded" and isinstance(updated, (int, float)):
            status = "recent" if current_time - updated < 300 else "idle"
        preview = _text(item.get("preview"))
        sessions.append(
            {
                "id": session_id,
                "provider": "codex",
                "name": _text(_first(item, "agentNickname"), "Codex"),
                "status": status.lower(),
                "summary": " ".join(preview.split())[:240],
                "updated_at": _iso_from_unix(updated),
                "cwd": _text(item.get("cwd")) or None,
                "files": [],
                "model": _text(item.get("modelProvider")) or None,
                "can_message": True,
            }
        )
    return sessions


def _codex_threads(repository: Path, timeout: float = 6.0) -> object:
    """Query Codex's documented app-server protocol over stdio."""
    process = subprocess.Popen(
        ["codex", "app-server", "--stdio"],
        cwd=repository,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    if process.stdin is None or process.stdout is None:  # pragma: no cover - Popen invariant.
        process.kill()
        raise TelemetryError("Codex app-server did not expose stdio")
    requests = [
        {
            "method": "initialize",
            "id": 1,
            "params": {
                "clientInfo": {
                    "name": "spidey_sense",
                    "title": "Spidey Sense",
                    "version": "0.7.0",
                },
                "capabilities": {"experimentalApi": True},
            },
        },
        {"method": "initialized", "params": {}},
        {
            "method": "thread/list",
            "id": 2,
            "params": {"limit": 12, "cwd": str(repository), "sortKey": "recency_at"},
        },
    ]
    try:
        for request in requests:
            process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        process.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if not selector.select(timeout=min(0.25, max(0.0, deadline - time.monotonic()))):
                    continue
                line = process.stdout.readline()
                if not line:
                    break
                response = json.loads(line)
                if isinstance(response, dict) and response.get("id") == 2:
                    if "error" in response:
                        raise TelemetryError(f"Codex app-server error: {response['error']}")
                    return response.get("result", {})
        raise TelemetryError("Codex app-server session query timed out")
    finally:
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive cleanup.
            process.kill()
            process.wait(timeout=1)
        process.stdin.close()
        process.stdout.close()


class LiveTelemetryCollector:
    """Collect observable local state without reading private transcript files."""

    def __init__(
        self,
        repository: str | Path,
        *,
        runner: CommandRunner | None = None,
        which: Callable[[str], str | None] | None = None,
        codex_loader: Callable[[Path, float], object] | None = None,
        session_ttl: float = 5.0,
    ) -> None:
        self.repository = Path(repository).expanduser().resolve()
        if not self.repository.is_dir():
            raise TelemetryError(f"repository is not a directory: {self.repository}")
        self.runner = runner or _default_runner
        self.which = which or shutil.which
        self.codex_loader = codex_loader or _codex_threads
        self.session_ttl = session_ttl
        self._session_cache: dict[str, object] | None = None
        self._session_cache_time = 0.0
        self._lock = threading.Lock()

    def snapshot(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "git": self._git_snapshot(),
            **self._session_snapshot(),
        }

    def _command(self, command: Sequence[str], timeout: float = 3.0) -> str:
        result = self.runner(command, self.repository, timeout)
        if result.returncode != 0:
            message = result.stderr.strip() or f"exit code {result.returncode}"
            raise TelemetryError(f"{' '.join(command[:2])}: {message}")
        return result.stdout

    def _git_snapshot(self) -> dict[str, object]:
        branch = self._command(["git", "branch", "--show-current"]).strip() or "detached"
        head_result = self.runner(["git", "rev-parse", "HEAD"], self.repository, 2.0)
        head = head_result.stdout.strip() if head_result.returncode == 0 else None
        remote_result = self.runner(["git", "remote", "get-url", "origin"], self.repository, 2.0)
        remote = remote_result.stdout.strip() if remote_result.returncode == 0 else None
        status_output = self._command(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"]
        )
        dirty_files: list[dict[str, str]] = []
        for line in status_output.splitlines():
            if len(line) < 4:
                continue
            path = line[3:].split(" -> ")[-1]
            dirty_files.append({"path": path, "status": line[:2].strip() or "modified"})

        log_result = self.runner(
            ["git", "log", "-8", "--format=%H%x1f%h%x1f%an%x1f%aI%x1f%s"],
            self.repository,
            3.0,
        )
        log_output = log_result.stdout if log_result.returncode == 0 else ""
        commits: list[dict[str, object]] = []
        for line in log_output.splitlines():
            parts = line.split("\x1f", 4)
            if len(parts) != 5:
                continue
            sha, short_sha, author, committed_at, subject = parts
            files_result = self.runner(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
                self.repository,
                2.0,
            )
            files = files_result.stdout.splitlines() if files_result.returncode == 0 else []
            commits.append(
                {
                    "sha": sha,
                    "short_sha": short_sha,
                    "author": author,
                    "committed_at": committed_at,
                    "subject": subject,
                    "files": files,
                }
            )
        return {
            "branch": branch,
            "head": head,
            "remote": remote,
            "dirty_files": dirty_files,
            "commits": commits,
        }

    def _session_snapshot(self) -> dict[str, object]:
        now = time.monotonic()
        with self._lock:
            if self._session_cache is not None and now - self._session_cache_time < self.session_ttl:
                return self._session_cache

            sessions: list[dict[str, object]] = []
            providers: dict[str, dict[str, object]] = {}
            for provider, executable, loader in (
                ("claude", "claude", self._load_claude),
                ("codex", "codex", self._load_codex),
                ("entire", "entire", self._load_entire),
            ):
                if self.which(executable) is None:
                    providers[provider] = {"available": False, "error": None}
                    continue
                try:
                    discovered = loader()
                    sessions.extend(discovered)
                    providers[provider] = {
                        "available": True,
                        "error": None,
                        "sessions": len(discovered),
                    }
                except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired, TelemetryError) as exc:
                    providers[provider] = {"available": True, "error": str(exc), "sessions": 0}

            sessions.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            self._session_cache = {"sessions": sessions, "providers": providers}
            self._session_cache_time = now
            return self._session_cache

    def _load_claude(self) -> list[dict[str, object]]:
        output = self._command(
            ["claude", "agents", "--json", "--all", "--cwd", str(self.repository)],
            timeout=5.0,
        )
        return normalise_claude_sessions(json.loads(output))

    def _load_codex(self) -> list[dict[str, object]]:
        return normalise_codex_threads(self.codex_loader(self.repository, 6.0))

    def _load_entire(self) -> list[dict[str, object]]:
        output = self._command(["entire", "session", "list", "--json"], timeout=5.0)
        return normalise_entire_sessions(json.loads(output))
