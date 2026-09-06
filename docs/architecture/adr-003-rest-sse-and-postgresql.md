# ADR-003: REST, server-sent events, and PostgreSQL for the MVP

## Status

Accepted for CP-001.

## Context

The shared platform needs durable team/plan state, idempotent connector ingestion,
and near-real-time visual updates. The initial team size and event rate are modest.

## Options considered

| Option | Benefits | Costs |
| --- | --- | --- |
| Three-second polling and JSON files | Already works locally | Poor multi-machine durability and unnecessary repeated work |
| REST + SSE + PostgreSQL | Familiar, transactional, simple one-way live stream | SSE is not a full bidirectional transport |
| WebSockets + broker + event sourcing | Flexible and highly real-time | More operations, reconnection, ordering, and projection complexity |

## Decision

Use PostgreSQL for shared source-of-truth data, REST for queries/commands/connector
events, and SSE for live browser projections. Retain JSON files and polling for local
demo mode. Use immutable event IDs and connector sequences for idempotency without
adopting full event sourcing.

## Rationale

- The browser primarily receives updates; mutations remain ordinary authenticated
  requests.
- PostgreSQL fits relational teams, roles, plans, assignments, and audit data.
- Idempotent ingestion handles network replay without a message broker.
- This is the least complex architecture that satisfies shared near-real-time state.

## Trade-offs and consequences

- Some derived state must be rebuilt or reconciled after missed events.
- Graph snapshots may need separate compressed storage as they grow.
- SSE connection limits and fan-out must be measured before hosted scale.
- Revisit WebSockets or a broker when true bidirectional streams, high fan-out, or
  sustained ingestion load is demonstrated.
