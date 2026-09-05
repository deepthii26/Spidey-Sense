# Live CLI integrations and control boundaries

Spidey Sense combines three kinds of observable truth:

1. current Git worktree changes and recent commits;
2. session metadata exposed by supported AI coding-agent interfaces; and
3. explicit teammate activity and human directives stored by Spidey Sense.

It does not scrape private chain-of-thought or claim to know internal model reasoning.

## Codex

Spidey Sense starts a short-lived local `codex app-server --stdio` process, performs
the documented initialization handshake, and calls `thread/list` scoped to the
repository. The adapter reads thread ID, public preview, provider, recency, and status.

When a human explicitly clicks **Send to Codex now**, Spidey Sense uses:

```bash
codex queue --thread THREAD_ID --message "DIRECTIVE"
```

No shell is involved and no other Codex operation is allowlisted. A separately
started app-server may report a recently active thread as `recent` rather than
`active`; worktree changes provide the complementary live signal.

Protocol reference: [OpenAI Codex app-server](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md).

## Claude Code

When Claude Code is installed, Spidey Sense calls:

```bash
claude agents --json --all --cwd /absolute/repository/path
```

This exposes active and completed background-session metadata intended for scripts.
The adapter accepts current snake-case and camel-case field variants and uses only
the session ID, name, status, public summary, timestamps, working directory, model,
and touched files when supplied.

Claude Code does not currently expose a queue command equivalent to Codex in its
documented CLI surface, so directives for Claude are stored in the shared inbox.

CLI reference: [Anthropic Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code/cli-usage).

## Entire

When Entire is installed, Spidey Sense calls:

```bash
entire session list --json
```

It maps `session_id`, `agent`, `model`, `status`, `worktree_path`, `last_active`,
`last_prompt`, and `files_touched` into the common live-session contract. Entire is
optional; the provider health panel shows `not installed` without affecting Git,
Codex, Claude, or manual activity.

CLI source: [Entire CLI](https://github.com/entireio/cli). See
[Entire compatibility](entire-compatibility.md) for checkpoint and semantic-graph
integration details.

## Git and GitHub

Local telemetry uses read-only Git commands to expose the branch, HEAD, remote,
working-tree changes, recent commit subjects, authors, timestamps, and changed files.
These values refresh with the dashboard's three-second polling loop.

The existing GitHub synchronizer separately reads merged pull requests, commits, and
changed files through the GitHub REST API. It can mark related teammate activity done
using stale-write protection.

## Human mission control

The dashboard supports two explicit actions:

- **Assign** updates a teammate's repository-relative files and status through
  `POST /api/activity`.
- **Queue directive** writes a message to `.spidey-sense/directives.json` through
  `POST /api/directives`.

Adapters can read and acknowledge inbox messages with:

```bash
python -m spidey_sense.live --pretty inbox
python -m spidey_sense.live ack DIRECTIVE_ID
```

This inbox provides a provider-neutral control seam without granting the dashboard
arbitrary terminal access.
