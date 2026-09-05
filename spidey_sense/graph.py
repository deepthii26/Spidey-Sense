"""File-level dependency graph construction for local git repositories."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Iterator


LANGUAGES = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".py": "python",
    ".pyi": "python",
}

JS_EXTENSIONS = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
JS_LIKE_EXTENSIONS = frozenset(JS_EXTENSIONS)


class GraphBuildError(RuntimeError):
    """Raised when a repository cannot be scanned."""


@dataclass(frozen=True)
class ImportReference:
    specifier: str
    kind: str
    line: int


def _run_git(repository: Path, *args: str) -> bytes:
    try:
        process = subprocess.run(
            ["git", "-C", str(repository), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise GraphBuildError(f"could not run git: {exc}") from exc

    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise GraphBuildError(detail or f"git command failed with exit code {process.returncode}")
    return process.stdout


def find_git_root(repository: str | Path) -> Path:
    requested = Path(repository).expanduser().resolve()
    if not requested.is_dir():
        raise GraphBuildError(f"repository is not a directory: {requested}")

    output = _run_git(requested, "rev-parse", "--show-toplevel")
    root = Path(output.decode("utf-8", errors="strict").strip()).resolve()
    if not root.is_dir():
        raise GraphBuildError(f"git returned an invalid repository root: {root}")
    return root


def scan_repository_files(root: Path) -> list[PurePosixPath]:
    """Return tracked and non-ignored untracked source files in stable order."""
    raw = _run_git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    paths: list[PurePosixPath] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        relative_text = item.decode("utf-8", errors="surrogateescape")
        relative = PurePosixPath(relative_text)
        if relative.suffix.lower() not in LANGUAGES:
            continue
        absolute = root.joinpath(*relative.parts)
        if absolute.is_file() and not absolute.is_symlink():
            paths.append(relative)
    return sorted(set(paths), key=str)


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _mask_js_comments(text: str) -> str:
    """Replace JS comments with spaces while preserving strings and line offsets."""
    output = list(text)
    index = 0
    state = "code"
    quote = ""

    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""

        if state == "code":
            if char in ("'", '"', "`"):
                state = "string"
                quote = char
            elif char == "/" and next_char == "/":
                output[index] = output[index + 1] = " "
                index += 1
                state = "line_comment"
            elif char == "/" and next_char == "*":
                output[index] = output[index + 1] = " "
                index += 1
                state = "block_comment"
        elif state == "string":
            if char == "\\":
                index += 1
            elif char == quote:
                state = "code"
        elif state == "line_comment":
            if char == "\n":
                state = "code"
            else:
                output[index] = " "
        elif state == "block_comment":
            if char == "*" and next_char == "/":
                output[index] = output[index + 1] = " "
                index += 1
                state = "code"
            elif char != "\n":
                output[index] = " "
        index += 1

    return "".join(output)


_STATIC_JS_IMPORT = re.compile(
    r"\b(?P<kind>import|export)\s+(?:type\s+)?"
    r"(?:[\w*$,{}\s]+?\s+from\s+)?"
    r"(?P<quote>['\"])(?P<specifier>[^'\"]+)(?P=quote)",
    re.MULTILINE,
)
_CALL_JS_IMPORT = re.compile(
    r"\b(?P<kind>require|import)\s*\(\s*"
    r"(?P<quote>['\"])(?P<specifier>[^'\"]+)(?P=quote)\s*\)",
    re.MULTILINE,
)


def parse_javascript_imports(text: str) -> list[ImportReference]:
    masked = _mask_js_comments(text)
    references: list[ImportReference] = []

    for pattern in (_STATIC_JS_IMPORT, _CALL_JS_IMPORT):
        for match in pattern.finditer(masked):
            kind = match.group("kind")
            if pattern is _CALL_JS_IMPORT and kind == "import":
                kind = "dynamic-import"
            elif kind == "export":
                kind = "re-export"
            references.append(
                ImportReference(
                    specifier=match.group("specifier"),
                    kind=kind,
                    line=_line_number(masked, match.start()),
                )
            )

    return sorted(set(references), key=lambda ref: (ref.line, ref.specifier, ref.kind))


def _normalise_relative_path(path: PurePosixPath) -> PurePosixPath | None:
    parts: list[str] = []
    for part in path.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return PurePosixPath(*parts)


def _package_json_entries(root: Path, directory: PurePosixPath) -> Iterator[str]:
    package_json = root.joinpath(*directory.parts, "package.json")
    if not package_json.is_file():
        return
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    for field in ("types", "module", "main"):
        value = data.get(field)
        if isinstance(value, str):
            yield value


def resolve_javascript_import(
    root: Path,
    source: PurePosixPath,
    specifier: str,
    available: set[PurePosixPath],
) -> PurePosixPath | None:
    clean_specifier = specifier.split("?", 1)[0].split("#", 1)[0]
    if not clean_specifier.startswith("."):
        return None

    base = _normalise_relative_path(source.parent / PurePosixPath(clean_specifier))
    if base is None:
        return None

    candidates: list[PurePosixPath] = [base]
    if base.suffix.lower() in JS_LIKE_EXTENSIONS:
        stem = base.with_suffix("")
        candidates.extend(PurePosixPath(f"{stem}{extension}") for extension in JS_EXTENSIONS)
    elif not base.suffix:
        candidates.extend(PurePosixPath(f"{base}{extension}") for extension in JS_EXTENSIONS)

    for entry in _package_json_entries(root, base):
        entry_path = _normalise_relative_path(base / PurePosixPath(entry))
        if entry_path is not None:
            candidates.append(entry_path)
            if not entry_path.suffix:
                candidates.extend(
                    PurePosixPath(f"{entry_path}{extension}") for extension in JS_EXTENSIONS
                )
    candidates.extend(base / f"index{extension}" for extension in JS_EXTENSIONS)

    for candidate in candidates:
        if candidate in available:
            return candidate
    return None


def _python_module_for_path(path: PurePosixPath) -> str:
    parts = list(path.parts)
    if parts and parts[0] in {"src", "python", "lib"}:
        parts.pop(0)
    filename = parts.pop()
    suffix = ".pyi" if filename.endswith(".pyi") else ".py"
    module_name = filename[: -len(suffix)]
    if module_name != "__init__":
        parts.append(module_name)
    return ".".join(parts)


def _build_python_module_index(paths: Iterable[PurePosixPath]) -> dict[str, PurePosixPath]:
    candidates: dict[str, list[PurePosixPath]] = {}
    for path in paths:
        if path.suffix.lower() not in {".py", ".pyi"}:
            continue
        full_module = ".".join(path.with_suffix("").parts)
        if full_module.endswith(".__init__"):
            full_module = full_module[: -len(".__init__")]
        aliases = {full_module, _python_module_for_path(path)}
        for module in aliases:
            if module:
                candidates.setdefault(module, []).append(path)

    return {
        module: sorted(options, key=lambda item: (len(item.parts), str(item)))[0]
        for module, options in candidates.items()
    }


def _resolve_python_name(module: str, index: dict[str, PurePosixPath]) -> PurePosixPath | None:
    current = module
    while current:
        if current in index:
            return index[current]
        current = current.rpartition(".")[0]
    return None


def parse_python_imports(
    text: str,
    source: PurePosixPath,
    module_index: dict[str, PurePosixPath],
) -> tuple[list[tuple[ImportReference, PurePosixPath]], str | None]:
    try:
        tree = ast.parse(text, filename=str(source))
    except SyntaxError as exc:
        return [], f"{exc.msg} (line {exc.lineno or 0})"

    current_module = _python_module_for_path(source)
    if source.stem == "__init__":
        current_package = current_module
    else:
        current_package = current_module.rpartition(".")[0]

    resolved: list[tuple[ImportReference, PurePosixPath]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = _resolve_python_name(alias.name, module_index)
                if target is not None:
                    resolved.append(
                        (ImportReference(alias.name, "import", node.lineno), target)
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                package_parts = current_package.split(".") if current_package else []
                keep = len(package_parts) - node.level + 1
                if keep < 0:
                    continue
                prefix = package_parts[:keep]
                if node.module:
                    prefix.extend(node.module.split("."))
                base_module = ".".join(prefix)
                display_module = "." * node.level + (node.module or "")
            else:
                base_module = node.module or ""
                display_module = base_module

            child_targets: list[tuple[str, PurePosixPath]] = []
            for alias in node.names:
                if alias.name == "*":
                    continue
                child_module = ".".join(part for part in (base_module, alias.name) if part)
                child = module_index.get(child_module)
                if child is not None:
                    child_targets.append((alias.name, child))

            if child_targets:
                for alias_name, target in child_targets:
                    specifier = f"{display_module}:{alias_name}"
                    resolved.append(
                        (ImportReference(specifier, "from-import", node.lineno), target)
                    )
            else:
                target = _resolve_python_name(base_module, module_index)
                if target is not None:
                    resolved.append(
                        (ImportReference(display_module, "from-import", node.lineno), target)
                    )

    return resolved, None


class DependencyGraphBuilder:
    """Build a deterministic file-level dependency graph for one git repository."""

    def __init__(self, repository: str | Path):
        self.root = find_git_root(repository)

    def build(self) -> dict[str, object]:
        paths = scan_repository_files(self.root)
        available = set(paths)
        python_index = _build_python_module_index(paths)

        nodes = [
            {
                "id": str(path),
                "path": str(path),
                "language": LANGUAGES[path.suffix.lower()],
            }
            for path in paths
        ]
        edges: list[dict[str, object]] = []
        diagnostics: list[dict[str, object]] = []

        for source in paths:
            absolute = self.root.joinpath(*source.parts)
            try:
                text = absolute.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                diagnostics.append(
                    {"file": str(source), "level": "error", "message": f"cannot read file: {exc}"}
                )
                continue

            language = LANGUAGES[source.suffix.lower()]
            if language in {"javascript", "typescript"}:
                references = parse_javascript_imports(text)
                for reference in references:
                    target = resolve_javascript_import(self.root, source, reference.specifier, available)
                    if target is None:
                        diagnostics.append(
                            {
                                "file": str(source),
                                "line": reference.line,
                                "level": "info",
                                "message": f"unresolved or external import: {reference.specifier}",
                            }
                        )
                        continue
                    edges.append(self._edge(source, target, reference))
            else:
                imports, syntax_error = parse_python_imports(text, source, python_index)
                if syntax_error:
                    diagnostics.append(
                        {"file": str(source), "level": "error", "message": syntax_error}
                    )
                    continue
                for reference, target in imports:
                    edges.append(self._edge(source, target, reference))

        unique_edges = {
            (
                str(edge["source"]),
                str(edge["target"]),
                str(edge["kind"]),
                str(edge["specifier"]),
                int(edge["line"]),
            ): edge
            for edge in edges
        }
        ordered_edges = [unique_edges[key] for key in sorted(unique_edges)]
        diagnostics.sort(key=lambda item: (str(item.get("file", "")), int(item.get("line", 0))))

        return {
            "schema_version": "1.0",
            "repository": str(self.root),
            "nodes": nodes,
            "edges": ordered_edges,
            "diagnostics": diagnostics,
            "stats": {
                "nodes": len(nodes),
                "edges": len(ordered_edges),
                "diagnostics": len(diagnostics),
            },
        }

    @staticmethod
    def _edge(
        source: PurePosixPath,
        target: PurePosixPath,
        reference: ImportReference,
    ) -> dict[str, object]:
        return {
            "source": str(source),
            "target": str(target),
            "kind": reference.kind,
            "specifier": reference.specifier,
            "line": reference.line,
        }


def build_dependency_graph(repository: str | Path) -> dict[str, object]:
    """Convenience API used by the CLI and future Spidey Sense phases."""
    return DependencyGraphBuilder(repository).build()
