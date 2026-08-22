# Contributing

## Testing

Run the suite from the repo root after installing the dev extras:

```bash
pip install -e ".[dev]"
make test          # full suite, enforces the coverage floor
pytest tests/ -v   # same suite, reports coverage but does not gate on it
```

Coverage is measured on every run but the floor is only applied by `make test`, `make verify-release`, and CI. That keeps single-file runs (`pytest tests/test_sizing.py`) usable: whole-package coverage on one test file is near zero, and a floor in `addopts` failed those runs unconditionally.

The README test-count line (`N tests cover ...`) is asserted by `tests/test_readme_test_count_claim.py`; when you add or remove tests, bump the README count in the same commit.

### Platform-skipped tests

A handful of tests skip on Windows because the underlying OS feature is unavailable or behaves differently. `pytest --collect-only` still counts them, so the README's `N tests cover ...` number is the same on every platform; only the pass/skip ratio shifts.

- `tests/test_references.py`: the two `os.symlink`-based tests use the module-level `_skip_symlink = pytest.mark.skipif(sys.platform == "win32", ...)` mark. `os.symlink` on Windows requires developer mode or admin privileges, so the symlink-escape coverage runs on Linux/macOS only.
- `tests/test_cli_history.py` and `tests/test_history_io.py`: each has one `pytest.mark.skipif(sys.platform == "win32", ...)` test exercising POSIX file-mode permission errors that Windows does not enforce identically.
- `tests/test_pre_commit.py`: both tests skip wherever the `pre-commit` binary is not installed. CI installs `pre-commit` so they run there; local runs without `pre-commit` show them as skipped.

## Releasing

Publishing is automated. Pushing an immutable patch tag (`v1.2.3`) triggers `.github/workflows/release.yml`, which builds the wheel and sdist, attests build provenance with `actions/attest-build-provenance`, and publishes to PyPI via trusted publishing (`pypa/gh-action-pypi-publish`). No manual `twine upload` or API token is involved. The moving `v1` tag is filtered out (`v*.*.*`) so it does not trigger a second publish.

Every release ends with two tags pointing at the same commit:

1. An immutable patch tag (e.g., `v1.2.3`) that you push, and that drives the release workflow.
2. A `v1` moving major tag that `release.yml` repoints for you.

Steps:

```bash
# Bump version in pyproject.toml, __init__.py, and CHANGELOG.md together, commit, push to main.
git push origin main
git tag v1.2.3
git push origin v1.2.3          # release.yml builds, attests, publishes, then moves v1
gh release create v1.2.3 --title "v1.2.3" --notes-file CHANGELOG_ENTRY.md
```

Do not move `v1` by hand. The `move-major-tag` job in `release.yml` repoints it through the Git refs API once the publish job succeeds, so the moving tag can never lag the latest patch. It was moved manually until v1.4.1, and the step was missed for both v1.3.0 and v1.4.1, leaving `@v1` on v1.2.3 for two months. The job skips prerelease tags (`v2.0.0-rc1`) that the `v*.*.*` trigger glob also matches, and creates the tag rather than updating it on the first release of a new major line.

The `v1` tag always tracks the latest patch in the v1.x line. This lets GitHub Action users pin `@v1` for automatic updates or `@v1.2.3` for an immutable pin.

### One-time PyPI trusted-publishing setup

Trusted publishing must be configured once on the PyPI side before the first automated release. In the `skillcheck` project settings on PyPI, add a GitHub Actions publisher with:

- Owner: `moonrunnerkc`
- Repository: `skillcheck`
- Workflow filename: `release.yml`
- Environment: `pypi`

Until this is configured, the `Publish to PyPI` step will fail with an OIDC trust error; the build and attestation steps still run.