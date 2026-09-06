# ADR-002: Local connector instead of an autonomous monitoring agent

## Status

Accepted for CP-001.

## Context

The platform must know what approved Codex, Claude Code, Entire, Git, and repository
sessions are doing across developer machines. A broad autonomous agent would create
unnecessary access, privacy, reliability, and explainability risks.

## Options considered

| Option | Benefits | Costs |
| --- | --- | --- |
| Manual activity only | Safest and simplest | Becomes stale and provides weak live visibility |
| Deterministic local connector | Live structured telemetry with narrow permissions | Requires installation, pairing, upgrades, and offline handling |
| Autonomous LLM monitoring agent | Flexible interpretation | Non-determinism, high privilege pressure, cost, privacy and trust risks |

## Decision

Install a deterministic Spidey Connector on each participating machine or worktree.
It uses documented provider interfaces, read-only Git observations, the existing
dependency scanner, explicit scopes, and typed events. It cannot accept arbitrary
shell commands.

An optional AI adviser may later summarize already-authorized evidence and propose
resolutions. Its output is advisory and requires human approval for mutations.

## Rationale

- Collection and access control must be predictable and testable.
- Existing provider adapters already normalize public metadata without scraping
  private reasoning.
- A local component can observe worktrees without uploading source code.
- Typed, auditable commands preserve the current shell-free safety boundary.

## Trade-offs and consequences

- The team must distribute, pair, update, and monitor connector versions.
- Offline events require buffering and idempotent replay.
- Provider API changes require adapter updates.
- Revisit autonomous assistance only after permissions, evidence citations, audit,
  retention, and human confirmation are enforced.
