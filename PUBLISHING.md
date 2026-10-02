# Publishing ttagent to PyPI — exact checklist

1. Bump `__version__` in `ttagent.py` (the single source of truth).
2. Bump `version` in `pyproject.toml` — `tests/test_package_sync.py`
   enforces byte-identity; CI enforces version consistency.
3. Add a `RELEASE_NOTES.md` section.
4. `python scripts/sync_package.py` (regenerate `ttagent/__init__.py`).
5. Full offline suite: `python -m unittest discover -s tests`.
6. CLI smoke: `python ttagent.py --version` and `python ttagent.py "!!!"`
   (expect exit 2, no traceback).
7. MCP smoke: `echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python mcp_server.py`
8. `python -m pip install --upgrade build twine`
9. `python -m build` → `twine check dist/*`
10. Tag: `git tag v1.0.x && git push origin v1.0.x` — the release
    workflow builds, smoke-tests, publishes to PyPI (secret
    `PYPI_API_TOKEN`), and creates the GitHub Release with the notes.
11. After publish: `pip install ttagent==1.0.x` in a clean venv, run
    `ttagent --version` and one real lookup.
