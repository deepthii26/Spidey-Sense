# Entire compatibility notes

Spidey Sense does not require Entire, but its core schemas deliberately leave two
adapter seams for teams that use the Entire CLI and Entire Graph.

These notes are based on the public contracts in:

- <https://github.com/entireio/cli>
- <https://github.com/entireio/entire-graph>

## Entire CLI session activity

`entire session current --json`, `entire session info --json`, and
`entire session list --json` share a structured session envelope containing the
fields Spidey Sense needs:

- `session_id`
- `agent` and optional `model`
- `status`
- `branch`, `worktree_id`, and `worktree_path`
- `started_at`, `ended_at`, and `last_active`
- `files_touched`
- checkpoint counts and `last_checkpoint_id`

A future activity adapter should invoke Entire's public JSON commands rather than
read `.entire` implementation files. It can map `files_touched` to the existing
activity `files`, `last_active` to `updated_at`, and an actively running session to
`working`. Human teammate identity must remain explicit because an Entire session's
`agent` field identifies the coding agent, not necessarily the human owner.

`entire status --json` is useful for setup health and summarized active-agent state,
but it intentionally omits session IDs and files. It is therefore not sufficient by
itself for Spidey Sense activity ingestion.

## Commit and checkpoint provenance

Entire links a code commit to checkpoint metadata with this commit trailer:

```text
Entire-Checkpoint: <checkpoint-id>
```

Phase 4 preserves commit messages from GitHub and extracts current 26-character
ULIDs plus legacy 12-character hexadecimal checkpoint IDs into each commit's
`entire_checkpoint_ids` array. A later dashboard can link merged work to an Entire
checkpoint without changing the GitHub synchronization schema.

## Entire Graph semantic snapshots

Entire Graph exports its complete graph with:

```bash
entire graph snapshot --repo . --format ndjson --worktree
```

The stream currently uses additive schema `1.x` records, including:

- header records with provider version, languages, capabilities, warnings, partial
  failures, and completeness data;
- `file` records with stable IDs, paths, and languages;
- symbol records with stable compound IDs and source locations;
- relation records with `from_id`, `to_id`, relation type, confidence, reason, and
  optional evidence.

A future graph adapter should accept any `1.x` minor, ignore unknown optional fields,
and reject unknown major versions. Entity relations can be projected to Blocker
Radar's file-level edges by joining relation endpoint symbol IDs to their file paths.
Multiple entity relations between the same file pair should be collapsed while
retaining confidence/evidence summaries for blocker tooltips.

The built-in Phase 1 parser remains the zero-install fallback for JavaScript,
TypeScript, and Python repositories. Entire Graph can later become an optional
higher-fidelity provider rather than a replacement that every user must install.
