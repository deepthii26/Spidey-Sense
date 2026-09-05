# Changelog

All notable changes to Spidey Sense are documented here.

## 0.6.0 — 2026-09-05

### Added

- Interactive React Three Fiber dependency city with selectable file buildings,
  dependency roads, conflict colors, and animated active-teammate beacons.
- All/active/conflicts scene filters, optional orbit, reduced-motion behavior,
  mobile DPR limiting, lazy loading, and a non-WebGL fallback.
- Read-only live Git branch, HEAD, remote, worktree, commit, and changed-file telemetry.
- Codex thread discovery through the documented app-server protocol.
- Claude Code background-session discovery through `claude agents --json`.
- Optional Entire session discovery through `entire session list --json`.
- Human mission assignment through `POST /api/activity`.
- Atomic human-to-agent directive inbox and `POST /api/directives`.
- Explicit direct Codex delivery through an allowlisted `codex queue` invocation.
- `spidey-sense-live` CLI for telemetry, inbox access, directive creation, and
  acknowledgements.
- Three-second visible-page dashboard refresh for near-real-time updates.

### Security

- Directive text is always handled as data and is never passed through a shell.
- Cross-origin write preflights are rejected and the server emits no CORS grants.
- Provider failures are isolated and exposed as health state rather than crashing
  the rest of the dashboard.

## 0.5.0 — 2026-09-05

- Initial Spidey Sense release containing the dependency graph, activity tracker,
  blocker detector, GitHub merged-PR synchronizer, pathway dashboard, sample data,
  tests, documentation, and CI.
