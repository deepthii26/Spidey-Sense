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
- [x] Phase 6 — Render files as an interactive 3D dependency city, animate active
  teammates, discover supported CLI sessions, stream Git state, and expose human
  mission assignment plus an auditable directive inbox.
- [x] Phase 6 visual identity — Group files into directory-based Web Zones, render
  imports as Web Strands, and surface active runners and danger signals in an
  original Spidey Sense radar theme.

The dependency-web view remains a presentation layer over the existing dashboard API; it does
not fork or duplicate graph and blocker logic.

## Likely next integrations

- Optional agent hooks that map Claude/Codex tool events directly to activity files.
- An Entire Graph adapter for higher-fidelity symbol relationships and evidence.
- Incremental graph updates for large monorepos.
- Configurable blocker rules and risk severity.
- Historical activity and blocker-resolution timelines.
- Optional team-hosted API and live updates.
- Additional language parsers driven by demonstrated team demand.

## Product principle

Spidey Sense should keep the warning explainable. Every visual alert must trace back
to a concrete same-file overlap or dependency edge, even as the visualization and
providers become more sophisticated.

## Collaborative platform checkpoints

The local prototype is now the foundation for a shared small-team product. The
architecture and ordered checkpoints are defined in
[`checkpoints/CP-001-architecture-foundation.md`](checkpoints/CP-001-architecture-foundation.md).

- [x] CP-001 — Align the collaborative platform architecture, connector boundary,
  team planning model, GitHub conflict evidence, security model, and two-branch
  workflow.
- [ ] CP-002 — Implement team, role, repository, plan, work-item, assignment,
  dependency, and checkpoint domains.
- [ ] CP-003 — Implement pairing and the privacy-scoped Spidey Connector protocol.
- [ ] CP-004 — Add live Team Lobby and Plan Web visualization with streamed updates.
- [ ] CP-005 — Add GitHub App webhooks, conflict incidents, and rule-based resolution
  guidance.
- [ ] CP-006 — Harden directive adapters, authorization, audit, retention,
  accessibility, and team isolation.
