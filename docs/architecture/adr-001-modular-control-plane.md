# ADR-001: Modular monolith control plane

## Status

Accepted for CP-001.

## Context

Spidey Sense must grow from a local prototype into a team platform supporting plans,
live connector events, GitHub, conflict detection, directives, and visualization.
The initial target is small teams and an MVP timeline.

## Options considered

| Option | Benefits | Costs |
| --- | --- | --- |
| Keep only the local process | Simplest and private | Cannot provide a shared team view across machines |
| Modular monolith control plane | Simple deployment, transactions, clear modules | Modules scale together initially |
| Microservices | Independent scaling and ownership | Operational, consistency, tracing, and deployment complexity |

## Decision

Build one deployable control plane with strong internal modules and PostgreSQL. Keep
the existing local mode available. Do not introduce microservices, a graph database,
or a message broker for the MVP.

## Rationale

- The product needs shared state, but expected initial scale does not justify a
  distributed system.
- Plans, assignments, blockers, directives, and audit events benefit from consistent
  transactions.
- Existing Python modules already demonstrate useful domain boundaries.
- Module extraction remains possible when measured scaling or ownership demands it.

## Trade-offs and consequences

- Deployment and development remain manageable for a small team.
- A failure can affect the complete control plane, so provider and job failures must
  remain isolated internally.
- Independent module scaling is deferred.
- Revisit when one workload dominates capacity, the engineering team exceeds roughly
  ten people, or separate reliability boundaries become necessary.
