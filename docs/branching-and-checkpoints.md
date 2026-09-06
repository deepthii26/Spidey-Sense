# Branching and checkpoint policy

Spidey Sense uses exactly two long-lived branches:

| Branch | Purpose | Direct development |
| --- | --- | --- |
| `main` | Stable, reviewed checkpoints suitable for release | No |
| `progress` | Integration branch for all active product work | Yes |

## Workflow

1. Begin work on `progress`.
2. Commit small, coherent changes with tests and documentation.
3. Record important product milestones as numbered checkpoints under
   `docs/checkpoints/`.
4. Validate the entire checkpoint on `progress`.
5. Merge `progress` into `main` only after the owner approves the checkpoint.
6. Continue the next checkpoint on `progress`.

No additional feature branches are part of the current workflow. This is deliberate:
the initial team is small, and the product itself is intended to make parallel work
on a shared integration branch visible. If the project grows beyond a small team,
this decision must be revisited because a single integration branch can become a
bottleneck.

## Commit convention

Use checkpoint-aware subjects when a commit establishes or completes a milestone:

```text
checkpoint 01: establish collaborative platform architecture
```

Ordinary implementation commits should state the behavior added or corrected. A
checkpoint record must describe its scope, acceptance criteria, validation evidence,
and promotion state.

## Promotion rule

`main` is not updated automatically. Promotion requires:

- all checkpoint acceptance criteria satisfied;
- backend and frontend validation passing;
- security/privacy impact reviewed;
- data-contract changes documented;
- an explicit owner decision to merge `progress` into `main`.
