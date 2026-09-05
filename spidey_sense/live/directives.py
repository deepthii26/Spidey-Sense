"""Auditable human directives for coding-agent sessions."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Sequence
from uuid import uuid4

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows has no fcntl.
    fcntl = None  # type: ignore[assignment]


class DirectiveStoreError(RuntimeError):
    """Raised for invalid or inaccessible directive data."""


class DirectiveDispatchError(DirectiveStoreError):
    """Raised when an explicit provider delivery fails."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _required_text(value: object, label: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DirectiveStoreError(f"{label} must not be empty")
    text = value.strip()
    if len(text) > maximum or any(character in text for character in ("\0", "\r")):
        raise DirectiveStoreError(f"{label} is invalid or longer than {maximum} characters")
    return text


class DirectiveStore:
    def __init__(self, path: str | Path = ".spidey-sense/directives.json") -> None:
        self.path = Path(path).expanduser().resolve()
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    def snapshot(self) -> dict[str, object]:
        with self._lock(exclusive=False):
            return self._read_unlocked()

    def create(
        self,
        *,
        teammate: object,
        message: object,
        provider: object = "inbox",
        session_id: object = None,
    ) -> dict[str, object]:
        teammate_text = _required_text(teammate, "teammate", maximum=120)
        message_text = _required_text(message, "message", maximum=4000)
        provider_text = _required_text(provider, "provider", maximum=40).lower()
        if provider_text not in {"inbox", "codex", "claude", "entire"}:
            raise DirectiveStoreError("provider must be one of: inbox, codex, claude, entire")
        session_text = None
        if session_id is not None:
            session_text = _required_text(session_id, "session_id", maximum=200)
        directive: dict[str, object] = {
            "id": str(uuid4()),
            "teammate": teammate_text,
            "message": message_text,
            "provider": provider_text,
            "session_id": session_text,
            "status": "queued",
            "created_at": _now(),
            "delivered_at": None,
            "error": None,
        }
        with self._lock(exclusive=True):
            data = self._read_unlocked()
            directives = data["directives"]
            assert isinstance(directives, list)
            directives.insert(0, directive)
            del directives[100:]
            self._write_unlocked(data)
        return directive

    def mark(self, directive_id: str, *, status: str, error: str | None = None) -> dict[str, object]:
        if status not in {"queued", "sent", "acknowledged", "failed"}:
            raise DirectiveStoreError("invalid directive status")
        with self._lock(exclusive=True):
            data = self._read_unlocked()
            directives = data["directives"]
            assert isinstance(directives, list)
            for directive in directives:
                if isinstance(directive, dict) and directive.get("id") == directive_id:
                    directive["status"] = status
                    directive["delivered_at"] = _now() if status == "sent" else directive.get("delivered_at")
                    directive["error"] = error
                    self._write_unlocked(data)
                    return directive
        raise DirectiveStoreError(f"directive not found: {directive_id}")

    @contextmanager
    def _lock(self, *, exclusive: bool) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock_file = self.lock_path.open("a+b")
        except OSError as exc:
            raise DirectiveStoreError(f"cannot open directive lock: {exc}") from exc
        with lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _read_unlocked(self) -> dict[str, object]:
        if not self.path.exists():
            return {"schema_version": "1.0", "directives": []}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DirectiveStoreError(f"cannot read directive store: {exc}") from exc
        if not isinstance(value, dict) or value.get("schema_version") != "1.0":
            raise DirectiveStoreError("unsupported directive store schema")
        if not isinstance(value.get("directives"), list):
            raise DirectiveStoreError("directive store 'directives' must be an array")
        return value

    def _write_unlocked(self, value: dict[str, object]) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(value, temporary, indent=2)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
        except OSError as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise DirectiveStoreError(f"cannot write directive store: {exc}") from exc


DispatchRunner = Callable[[Sequence[str], Path, float], subprocess.CompletedProcess[str]]


def _dispatch_runner(
    command: Sequence[str], cwd: Path, timeout: float
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command), cwd=cwd, text=True, capture_output=True, check=False, timeout=timeout
    )


class DirectiveDispatcher:
    """Deliver an explicit directive through an allowlisted provider command."""

    def __init__(
        self,
        store: DirectiveStore,
        repository: str | Path,
        *,
        runner: DispatchRunner | None = None,
    ) -> None:
        self.store = store
        self.repository = Path(repository).expanduser().resolve()
        self.runner = runner or _dispatch_runner

    def dispatch(self, directive: dict[str, object]) -> dict[str, object]:
        provider = directive.get("provider")
        session_id = directive.get("session_id")
        if provider != "codex":
            raise DirectiveDispatchError(
                "direct delivery is currently supported only for Codex; this directive remains in the inbox"
            )
        if not isinstance(session_id, str) or not session_id:
            raise DirectiveDispatchError("a Codex thread id is required for direct delivery")
        message = directive.get("message")
        if not isinstance(message, str):  # pragma: no cover - store guarantees this.
            raise DirectiveDispatchError("directive message is invalid")
        try:
            result = self.runner(
                ["codex", "queue", "--thread", session_id, "--message", message],
                self.repository,
                15.0,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.store.mark(str(directive["id"]), status="failed", error=str(exc))
            raise DirectiveDispatchError(f"Codex delivery failed: {exc}") from exc
        if result.returncode != 0:
            error = result.stderr.strip() or f"exit code {result.returncode}"
            self.store.mark(str(directive["id"]), status="failed", error=error)
            raise DirectiveDispatchError(f"Codex delivery failed: {error}")
        return self.store.mark(str(directive["id"]), status="sent")
