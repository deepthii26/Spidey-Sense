# JSON data contracts

Spidey Sense uses versioned JSON at module boundaries. Paths inside a repository are
normalized to POSIX-style, repository-relative strings.

## Dependency graph

Edges point from an importing file (`source`) to the local file it depends on
(`target`).

```json
{
  "schema_version": "1.0",
  "repository": "/work/project",
  "nodes": [
    {"id": "src/app.ts", "path": "src/app.ts", "language": "typescript"}
  ],
  "edges": [
    {
      "source": "src/app.ts",
      "target": "src/core.ts",
      "kind": "import",
      "specifier": "./core",
      "line": 1
    }
  ],
  "diagnostics": [],
  "stats": {"nodes": 2, "edges": 1, "diagnostics": 0}
}
```

Diagnostics report syntax errors, unresolved local-looking imports, and external
package imports without turning them into graph edges.

## Activity store

The activity store contains the latest complete record for each teammate.

```json
{
  "schema_version": "1.0",
  "teammates": {
    "alice": {
      "teammate": "alice",
      "files": ["src/core.ts"],
      "status": "working",
      "updated_at": "2026-09-05T10:30:00.000000Z"
    }
  }
}
```

Allowed statuses are `pending`, `working`, and `done`. Teammate keys are normalized
for lookup while the record retains the display name.

## Blocker list

The blocker CLI emits a plain array. Dependency blockers include the original graph
edge so a UI can explain the relationship.

```json
[
  {
    "blocking_teammate": "alice",
    "blocked_teammate": "bob",
    "type": "dependency",
    "blocking_file": "src/core.ts",
    "blocked_file": "src/app.ts",
    "reciprocal": false,
    "dependency": {
      "source": "src/app.ts",
      "target": "src/core.ts",
      "kind": "import",
      "specifier": "./core",
      "line": 1
    }
  }
]
```

`type` is either `dependency` or `same_file`. Same-file conflicts set `reciprocal`
to `true` and generate one record in each direction.

## GitHub synchronization result

The synchronizer reports inspected merges, applied activity updates, and updates
skipped because the underlying activity changed.

```json
{
  "schema_version": "1.0",
  "repository": "owner/repository",
  "checked_at": "2026-09-05T12:00:00.000000Z",
  "merged_pull_requests": [],
  "updates": [],
  "skipped_updates": []
}
```

Commit entries may include `entire_checkpoint_ids`, extracted from
`Entire-Checkpoint` commit trailers.

## Dashboard aggregate

`GET /api/dashboard` returns the latest inputs in one response:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-09-05T12:05:00.000000Z",
  "repository": "/work/project",
  "graph": {
    "schema_version": "1.0",
    "repository": "/work/project",
    "nodes": [],
    "edges": [],
    "diagnostics": [],
    "stats": {"nodes": 0, "edges": 0, "diagnostics": 0}
  },
  "activity": {"schema_version": "1.0", "teammates": {}},
  "blockers": [],
  "github_sync": null
}
```

`github_sync` is `null` when no synchronization result file is configured. Consumers
should use `schema_version` and ignore unknown additive fields within the same major
version.
