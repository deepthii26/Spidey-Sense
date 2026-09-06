# Contributing to Spidey Sense

Contributions are welcome. Keep changes aligned with the project's local-first,
modular design and preserve the JSON contracts between phases.

## Development setup

```bash
git clone https://github.com/Preethesh16/Spidey-Sense.git
cd Spidey-Sense
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .

cd frontend
npm install
cd ..
```

## Run the test suite

```bash
python -m unittest discover -s tests -v

cd frontend
npm run typecheck
npm test
npm run build
```

Add or update tests whenever behavior changes. Graph changes should cover resolution
and diagnostics, store changes should consider concurrent writes, and blocker changes
should verify directionality and deduplication.

## Local dashboard development

In one terminal, serve the API and production frontend:

```bash
python -m spidey_sense.dashboard \
  --repository . \
  --activity examples/activity.json \
  --github-sync examples/github-sync.json
```

For frontend hot reload, run the Python server on port 8765 and then run
`npm run dev` inside `frontend`. Vite proxies `/api` to the local server.

## Pull requests

- Keep a pull request focused on one behavior or integration.
- Explain the coordination problem being solved and how it was verified.
- Document changes to CLI flags or JSON output.
- Never commit GitHub tokens, local activity files, generated builds, or dependency
  folders.
- Preserve accessibility for status, blocker, and tooltip information.

## Adding an integration

Prefer adapters that map external data into an existing Spidey Sense contract. For
example, a coding-agent session adapter should write the activity schema rather than
couple the blocker engine directly to that agent's private state.

New JSON fields should be additive within schema `1.x`. A breaking change requires a
new major schema version and a migration note.
