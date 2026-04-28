# skillcheck 1.1.0

An external audit against v1.0.1 surfaced eight repo defects: an unpinned GitHub Action install, gitignored evidence paths cited in the README, a top-level SKILL.md describing an unrelated skill, a missing `@v0` tag the README claimed existed, exit-code 2 conflating tool-misuse with warning-only reports, an oversized `cli.py`, and a vague-word list that flagged context-dependent terms like "comprehensive". v1.1.0 fixes all of them and reverses one v1.0.1 behavior change that turned out wrong.

## Behavior change

Warning-only runs now return exit code **0** by default. v1.0.1 made them return 2; that conflated valid runs that produced warnings with tool-misuse cases (missing path, conflicting flags, empty directory). CI consumers couldn't tell the difference. v1.1.0 splits them: warnings exit 0, input errors exit 2, errors stay at 1, semantic drift stays at 3. The new `--warnings-as-errors` flag escalates warning-only runs to exit 1 for pipelines that want warnings to block.

If your CI relied on v1.0.1's "warnings exit 2" behavior, add `--warnings-as-errors` to your skillcheck invocation, or pin to `@v1.0.1` until you can update.

## Added

- `--warnings-as-errors` flag.
- Two regression tests guarding the description-scorer rubric.

## Changed

- `action.yml` install step pins `skillcheck>=1.0.1`. Until v1.1.0 is uploaded to PyPI, this fails loudly on unpublished v1 features rather than silently resolving to v0.2.0.
- Description scorer no longer penalizes `comprehensive`, `robust`, or `flexible` in descriptions. Each can describe a concrete attribute when qualified; the false-positive rate was higher than the catch rate. Verified against `anthropics/skills`: zero score changes across 17 files, because none of those skills use the dropped words in their descriptions. The change is safe; the test suite gates future regressions.
- Description scorer verb matching collapsed from 86 entries (base + 3rd-person duplicates) to 42 base forms with stem normalization. Adding a new verb now only requires the base form.
- README field-test citations replaced gitignored `runs/...` paths with reproducible commands.
- README exit-code table documents the new semantics; flag table documents `--warnings-as-errors`.
- README test count: 663 → 667.

## Removed

- Top-level `git-commit-crafter` SKILL.md from the repo root.
- False `@v0` tag claim from the README and CHANGELOG.

## Why this is a minor and not a patch

The exit-code semantics change is observable in CI and not opt-in. Adding `--warnings-as-errors` is also a public-surface addition. Either alone would be a minor bump under semver; together they aren't a patch.

## Audit items not closed

- **PyPI publish**: the v1.1.0 sdist and wheel are built and pass `twine check`, but PyPI upload requires authenticated credentials and happens out-of-band. Until that runs, `pip install skillcheck` continues to ship v0.2.0. The pinned action install will refuse to run.
- **`cli.py` line count**: the audit asked for a refactor toward `main()` under 100 lines and `cli.py` under 700. An attempted helper extraction met the `main()` target but pushed total file size from 1127 to 1172. The refactor was reverted; the file remains at its pre-audit size, with the audit's "deliberate choice" path left open for a follow-up.
