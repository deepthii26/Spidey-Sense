# Security

Spidey Sense analyzes local source structure and can optionally query GitHub. Treat
repository paths, active filenames, teammate identities, and merge metadata as
potentially sensitive project information.

## Supported version

The latest version on the default branch receives security fixes.

## GitHub credentials

- Supply tokens through `GITHUB_TOKEN` or the environment variable named by
  `--token-env`.
- Use the narrowest repository read permission that supports pull-request and commit
  inspection.
- Tokens are placed only in request headers and are not persisted in activity or
  synchronization JSON.
- Pagination links must remain on the configured API origin, preventing credential
  forwarding to another host.
- Never commit `.env` files or tokens. If a token is exposed, revoke it immediately.

## Local server

The dashboard binds to `127.0.0.1` by default. Binding to `0.0.0.0` makes project
coordination data reachable from other hosts allowed by the machine's network and
firewall configuration. Do that only on a trusted network and place authentication
or a protected reverse proxy in front of it when needed.

The built-in server is intended for local development and demonstrations, not as a
public internet deployment.

Dashboard writes require JSON requests. The browser receives no cross-origin
permission headers, and `OPTIONS` requests are rejected, preventing an unrelated web
origin from silently reading or writing mission-control data.

## Agent directives

Spidey Sense never executes directive text as a shell command. A direct Codex send
uses an argument array equivalent to `codex queue --thread ID --message TEXT`; the
thread ID and message are passed as values rather than interpolated into a shell.
Other providers remain inbox-only. Direct delivery is always initiated by an
explicit dashboard or CLI action and is retained in the directive audit trail.

## Local files

`.spidey-sense/` is ignored by Git because it may reveal current work. Custom
activity and synchronization output paths should also remain uncommitted unless they
contain deliberate sample data.

## Reporting a vulnerability

Please use GitHub's private security-advisory reporting for
`Preethesh16/SpideySense` when available. Otherwise, open a minimal issue that asks
the maintainer for a private contact channel without publishing exploit details or
credentials.
