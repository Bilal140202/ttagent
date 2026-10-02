# Contributing to ttagent

Read, in order: `README.md` → `agent.md` → `agents.md` → `PROJECT_CONTEXT.md`.
If a PR contradicts those documents, the documents win — or the PR must
explicitly amend them.

## Ground rules (mirrors the sibling projects xthread-agent / ytagent / igagent)

1. Single file, stdlib only, Python 3.9+. If your change needs a pip
   dependency, it needs a very good reason and a `PROJECT_CONTEXT.md` entry.
2. Nothing personal in the repo: no real handles, video ids, or CDN URLs
   in tests, fixtures, or issues. Synthetic data only.
3. Logs on stderr, data on stdout. `--json` stdout is exactly one object.
4. Every new behavior ships with tests. The suite is offline and fast —
   network tests are a design bug.
5. Stable error codes are a public contract. Never rename one.
6. Envelope changes bump `SCHEMA_VERSION` and update
   `schema/video-result.schema.json` in the same commit.
7. After touching `ttagent.py`, run `python scripts/sync_package.py` — the
   package copy must stay byte-identical (CI enforces it).
8. Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).

## Dev setup

```bash
python -m venv .venv && source .venv/bin/activate   # optional
python -m unittest discover -s tests -p "test_*.py" # must be green, offline
```

## PR checklist

- [ ] Tests green, offline, < 5s
- [ ] `python scripts/sync_package.py --check` passes
- [ ] No real IDs/accounts anywhere
- [ ] `agent.md` updated if behavior/contract changed
- [ ] `docs/endpoint-matrix.md` updated if a slot's behavior was verified
