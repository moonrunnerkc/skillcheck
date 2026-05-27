# Contributing

## Testing

Run the suite from the repo root after installing the dev extras:

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

The README test-count line (`N tests cover ...`) is asserted by `tests/test_readme_test_count_claim.py`; when you add or remove tests, bump the README count in the same commit.

### Platform-skipped tests

A handful of tests skip on Windows because the underlying OS feature is unavailable or behaves differently. `pytest --collect-only` still counts them, so the README's `N tests cover ...` number is the same on every platform; only the pass/skip ratio shifts.

- `tests/test_references.py`: the two `os.symlink`-based tests use the module-level `_skip_symlink = pytest.mark.skipif(sys.platform == "win32", ...)` mark. `os.symlink` on Windows requires developer mode or admin privileges, so the symlink-escape coverage runs on Linux/macOS only.
- `tests/test_cli_history.py` and `tests/test_history_io.py`: each has one `pytest.mark.skipif(sys.platform == "win32", ...)` test exercising POSIX file-mode permission errors that Windows does not enforce identically.
- `tests/test_pre_commit.py`: both tests skip wherever the `pre-commit` binary is not installed. CI installs `pre-commit` so they run there; local runs without `pre-commit` show them as skipped.

## Releasing

Every release pushes two tags pointing to the same commit:

1. An immutable patch tag (e.g., `v1.2.3`).
2. A force-updated `v1` moving major tag pointing to the same commit.

Steps:

```bash
# Bump version in pyproject.toml, commit, push to main.
git push origin main
git tag v1.2.3
git push origin v1.2.3
git tag -f v1
git push origin v1 --force
gh release create v1.2.3 --title "v1.2.3" --notes-file CHANGELOG_ENTRY.md
```

The `v1` tag always tracks the latest patch in the v1.x line. This lets GitHub Action users pin `@v1` for automatic updates or `@v1.2.3` for an immutable pin.