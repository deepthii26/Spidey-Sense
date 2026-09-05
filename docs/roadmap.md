# Roadmap

Spidey Sense was built in ordered phases so every layer worked independently before
the next one depended on it.

## Completed

- [x] Phase 1 — Parse JavaScript, TypeScript, and Python imports into a reusable
  file dependency graph.
- [x] Phase 2 — Track teammate files, pending/working/done state, and update time in
  a concurrency-safe local JSON store.
- [x] Phase 3 — Detect directed dependency blockers and reciprocal same-file
  conflicts.
- [x] Phase 4 — Read merged pull requests through the GitHub REST API and safely
  mark overlapping activity done.
- [x] Phase 5 — Render responsive teammate pathways, checkpoint status, and blocker
  explanations in a React dashboard.

## Stretch goal

- [ ] Phase 6 — Add an optional game-like city skin where files or modules become
  buildings and dependency relationships become roads or routes.

The city view should remain a presentation layer over the existing dashboard API;
it must not fork or duplicate graph and blocker logic.

## Likely next integrations

- Automatic activity ingestion from Claude Code, Codex CLI, editor events, or a
  local file watcher.
- An Entire CLI session adapter using its public JSON output.
- An Entire Graph adapter for higher-fidelity symbol relationships.
- Incremental graph updates for large monorepos.
- Configurable blocker rules and risk severity.
- Historical activity and blocker-resolution timelines.
- Optional team-hosted API and live updates.
- Additional language parsers driven by demonstrated team demand.

## Product principle

Spidey Sense should keep the warning explainable. Every visual alert must trace back
to a concrete same-file overlap or dependency edge, even as the visualization and
providers become more sophisticated.
