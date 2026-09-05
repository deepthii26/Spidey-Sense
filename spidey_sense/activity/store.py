"""Atomic local JSON storage for teammate activity snapshots."""

from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator, Literal, Sequence, cast

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows has no fcntl.
    fcntl = None  # type: ignore[assignment]


Status = Literal["pending", "working", "done"]
VALID_STATUSES: tuple[Status, ...] = ("pending", "working", "done")
SCHEMA_VERSION = "1.0"


class ActivityStoreError(RuntimeError):
    """Base exception for activity storage failures."""


class ActivityValidationError(ActivityStoreError):
    """Raised for invalid teammate activity data."""


class ActivityNotFoundError(ActivityStoreError):
    """Raised when a requested teammate has no activity record."""


def _normalise_teammate(teammate: str) -> str:
    value = teammate.strip()
    if not value:
        raise ActivityValidationError("teammate must not be empty")
    if any(character in value for character in ("\0", "\n", "\r")):
        raise ActivityValidationError("teammate must be a single line of text")
    return value


def _normalise_file(file_path: str) -> str:
    value = file_path.strip().replace("\\", "/")
    if not value:
        raise ActivityValidationError("file paths must not be empty")
    if "\0" in value:
        raise ActivityValidationError("file paths must not contain NUL characters")
    if re.match(r"^[A-Za-z]:/", value):
        raise ActivityValidationError(f"file path must be repository-relative: {file_path}")

    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ActivityValidationError(f"file path must be repository-relative: {file_path}")
    normalised = str(path)
    if normalised in {"", "."}:
        raise ActivityValidationError("file paths must name a file")
    return normalised


def _normalise_files(files: Sequence[str]) -> tuple[str, ...]:
    if not files:
        raise ActivityValidationError("at least one file is required")
    return tuple(dict.fromkeys(_normalise_file(file_path) for file_path in files))


def _normalise_status(status: str) -> Status:
    if status not in VALID_STATUSES:
        choices = ", ".join(VALID_STATUSES)
        raise ActivityValidationError(f"status must be one of: {choices}")
    return cast(Status, status)


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ActivityStoreError("activity clock must return a timezone-aware datetime")
    utc_value = value.astimezone(timezone.utc)
    return utc_value.isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class ActivityRecord:
    teammate: str
    files: tuple[str, ...]
    status: Status
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "teammate": self.teammate,
            "files": list(self.files),
            "status": self.status,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, teammate: str, data: object) -> "ActivityRecord":
        if not isinstance(data, dict):
            raise ActivityStoreError(f"activity for {teammate!r} must be a JSON object")
        files = data.get("files")
        status = data.get("status")
        updated_at = data.get("updated_at")
        if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
            raise ActivityStoreError(f"activity files for {teammate!r} must be a JSON string array")
        if not isinstance(status, str):
            raise ActivityStoreError(f"activity status for {teammate!r} must be a string")
        if not isinstance(updated_at, str) or not updated_at:
            raise ActivityStoreError(f"activity timestamp for {teammate!r} must be a string")
        try:
            return cls(
                teammate=_normalise_teammate(teammate),
                files=_normalise_files(files),
                status=_normalise_status(status),
                updated_at=updated_at,
            )
        except ActivityValidationError as exc:
            raise ActivityStoreError(f"invalid stored activity for {teammate!r}: {exc}") from exc


class ActivityStore:
    """Persist the latest activity snapshot for each teammate in one JSON file.

    Updates use a sidecar lock on POSIX systems and always replace the JSON file
    atomically, preventing readers from observing partial writes.
    """

    def __init__(
        self,
        path: str | Path = ".spidey-sense/activity.json",
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path).expanduser().resolve()
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def snapshot(self) -> dict[str, object]:
        with self._lock(exclusive=False):
            records = self._read_unlocked()
        return self._serialise(records)

    def get(self, teammate: str) -> ActivityRecord:
        teammate = _normalise_teammate(teammate)
        with self._lock(exclusive=False):
            records = self._read_unlocked()
        try:
            return records[teammate]
        except KeyError as exc:
            raise ActivityNotFoundError(f"no activity found for teammate: {teammate}") from exc

    def upsert(self, teammate: str, files: Sequence[str], status: str) -> ActivityRecord:
        teammate = _normalise_teammate(teammate)
        normalised_files = _normalise_files(files)
        normalised_status = _normalise_status(status)
        record = ActivityRecord(
            teammate=teammate,
            files=normalised_files,
            status=normalised_status,
            updated_at=_format_timestamp(self._clock()),
        )
        with self._lock(exclusive=True):
            records = self._read_unlocked()
            records[teammate] = record
            self._write_unlocked(records)
        return record

    def update_status(self, teammate: str, status: str) -> ActivityRecord:
        teammate = _normalise_teammate(teammate)
        normalised_status = _normalise_status(status)
        with self._lock(exclusive=True):
            records = self._read_unlocked()
            if teammate not in records:
                raise ActivityNotFoundError(f"no activity found for teammate: {teammate}")
            previous = records[teammate]
            record = ActivityRecord(
                teammate=teammate,
                files=previous.files,
                status=normalised_status,
                updated_at=_format_timestamp(self._clock()),
            )
            records[teammate] = record
            self._write_unlocked(records)
        return record

    def update_status_if_current(
        self,
        teammate: str,
        status: str,
        *,
        expected_updated_at: str,
        expected_files: Sequence[str],
    ) -> ActivityRecord | None:
        """Update status only if the activity snapshot has not changed.

        This compare-and-set operation prevents an asynchronous integration from
        applying an old event to newly assigned work for the same teammate.
        """
        teammate = _normalise_teammate(teammate)
        normalised_status = _normalise_status(status)
        normalised_files = _normalise_files(expected_files)
        with self._lock(exclusive=True):
            records = self._read_unlocked()
            if teammate not in records:
                raise ActivityNotFoundError(f"no activity found for teammate: {teammate}")
            previous = records[teammate]
            if previous.updated_at != expected_updated_at or previous.files != normalised_files:
                return None
            record = ActivityRecord(
                teammate=teammate,
                files=previous.files,
                status=normalised_status,
                updated_at=_format_timestamp(self._clock()),
            )
            records[teammate] = record
            self._write_unlocked(records)
        return record

    def remove(self, teammate: str) -> bool:
        teammate = _normalise_teammate(teammate)
        with self._lock(exclusive=True):
            records = self._read_unlocked()
            if teammate not in records:
                return False
            del records[teammate]
            self._write_unlocked(records)
        return True

    @contextmanager
    def _lock(self, *, exclusive: bool) -> Iterator[None]:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            lock_file = self.lock_path.open("a+b")
        except OSError as exc:
            raise ActivityStoreError(f"cannot open activity store lock {self.lock_path}: {exc}") from exc

        with lock_file:
            if fcntl is not None:
                operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                fcntl.flock(lock_file.fileno(), operation)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _read_unlocked(self) -> dict[str, ActivityRecord]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ActivityStoreError(
                f"activity store contains invalid JSON at line {exc.lineno}, column {exc.colno}"
            ) from exc
        except (OSError, UnicodeError) as exc:
            raise ActivityStoreError(f"cannot read activity store {self.path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ActivityStoreError("activity store root must be a JSON object")
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ActivityStoreError(
                f"unsupported activity store schema: {data.get('schema_version')!r}"
            )
        teammates = data.get("teammates")
        if not isinstance(teammates, dict):
            raise ActivityStoreError("activity store 'teammates' must be a JSON object")
        return {
            teammate: ActivityRecord.from_dict(teammate, record)
            for teammate, record in teammates.items()
            if isinstance(teammate, str)
        }

    def _write_unlocked(self, records: dict[str, ActivityRecord]) -> None:
        payload = json.dumps(self._serialise(records), indent=2, sort_keys=False) + "\n"
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
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
        except OSError as exc:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise ActivityStoreError(f"cannot write activity store {self.path}: {exc}") from exc

    @staticmethod
    def _serialise(records: dict[str, ActivityRecord]) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "teammates": {
                teammate: records[teammate].to_dict()
                for teammate in sorted(records, key=str.casefold)
            },
        }
