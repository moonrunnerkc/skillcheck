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

Publishing is automated. Pushing an immutable patch tag (`v1.2.3`) triggers `.github/workflows/release.yml`, which builds the wheel and sdist, attests build provenance with `actions/attest-build-provenance`, and publishes to PyPI via trusted publishing (`pypa/gh-action-pypi-publish`). No manual `twine upload` or API token is involved. The moving `v1` tag is filtered out (`v*.*.*`) so it does not trigger a second publish.

Every release pushes two tags pointing to the same commit:

1. An immutable patch tag (e.g., `v1.2.3`) that drives the release workflow.
2. A force-updated `v1` moving major tag pointing to the same commit.

Steps:

```bash
# Bump version in pyproject.toml, __init__.py, and CHANGELOG.md together, commit, push to main.
git push origin main
git tag v1.2.3
git push origin v1.2.3          # release.yml builds, attests, and publishes to PyPI
git tag -f v1
git push origin v1 --force      # moving tag; filtered out of release.yml
gh release create v1.2.3 --title "v1.2.3" --notes-file CHANGELOG_ENTRY.md
```

The `v1` tag always tracks the latest patch in the v1.x line. This lets GitHub Action users pin `@v1` for automatic updates or `@v1.2.3` for an immutable pin.

### One-time PyPI trusted-publishing setup

Trusted publishing must be configured once on the PyPI side before the first automated release. In the `skillcheck` project settings on PyPI, add a GitHub Actions publisher with:

- Owner: `moonrunnerkc`
- Repository: `skillcheck`
- Workflow filename: `release.yml`
- Environment: `pypi`

Until this is configured, the `Publish to PyPI` step will fail with an OIDC trust error; the build and attestation steps still run.