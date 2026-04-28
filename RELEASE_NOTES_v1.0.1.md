# skillcheck 1.0.1

skillcheck v1.0.1 commits a batch of post-v1.0.0 implementation work that had been sitting uncommitted, ships the docs corrections an end-to-end verification surfaced, and aligns the README, CHANGELOG, and CLI surface so they describe the same release.

There is one behavior change relative to v1.0.0: warning-only runs now return exit code 2. Errors return 1; semantic drift returns 3. CI consumers that previously relied on warning-only exiting 0 must update.

## Changed

- Warning-only CLI reports now return exit code 2. Exit code 1 remains errors; exit code 3 remains semantic drift.
- README Exit Codes table row 0 now reads "no errors and no warnings".
- README test count corrected from 653 to 663.
- README JSON-stability promise updated from "0.x series" to "v1.x series".
- README field-test numbers reframed as April 2026 snapshots against `anthropics/skills`, with a note that they will drift as upstream evolves.
- `action.yml` `format` input description clarified: accepted but ignored at runtime; the action always invokes skillcheck with `--format json` so it can parse diagnostics for PR annotations and the step summary.
- Development extras now include `ruff>=0.6`, `mypy>=1.10`, and `types-PyYAML>=6.0`.

## Added

- `--semantic`: guide-compatible shortcut that enables semantic-adjacent validation. In standalone mode it runs heuristic graph analysis; with ingested agent responses it merges those diagnostics.
- `--agent-reason`: guide-compatible agent-workflow shortcut. Emits a combined critique and graph prompt packet so the calling agent can run both reasoning steps and feed JSON back through `--ingest-critique` and `--ingest-graph`.
- `--format md` and `--format agent`: Markdown report output and agent-oriented next-action output.
- `skillcheck.toml` config loading: top-level defaults for format, thresholds, target agent, strict VS Code mode, skip flags, ignored rule prefixes, graph analysis, semantic mode, history, and agent variants. CLI flags always win; the loader fills unset values.
- Experimental `--activation-hypotheses`: generates likely natural-language routing triggers plus a discoverability entropy score. Routing caveat included in every report.
- Machine-readable diagnostic metadata: JSON diagnostics now include `source` and `confidence` fields.
- GitHub Action inputs for the v1.0 modes: `semantic`, `analyze-graph`, `ingest-critique`, `critique-agent`, `ingest-graph`, `graph-agent`, `history`, `activation-hypotheses`. The action still always emits JSON internally for PR annotations.

## Why this is a patch and not a minor

Every addition above either documents existing behavior, refines a flag, or is gated behind a new opt-in flag. There is one breaking-ish change: warning-only runs now exit 2 instead of 0. Strict semver would call that a minor bump. The judgment call here: v1.0.0 shipped with documentation that already implied the v2-style exit codes (and the v1.0.1 README makes it explicit), the prior "warnings exit 0" behavior was undocumented in the released README, and the change matches what users running this in CI would expect. If your CI pipeline depended on the old behavior, pin to `@v1.0.0` rather than `@v1` until you can update.

## Verification

After installing `skillcheck==1.0.1`:

```bash
skillcheck --version
# skillcheck 1.0.1

skillcheck skills/skillcheck/SKILL.md --analyze-graph
# exit 0 with no errors and no warnings (only INFO diagnostics)
```

End-to-end verification was run against `anthropics/skills` at commit `5128e186` (18 SKILL.md files). All 26 documented flags exercised; all four exit codes (0, 1, 2, 3) reproduced; the action entrypoint produced byte-identical JSON to the CLI. Full report: see the v1.0.1 verification artifacts.

## Links

- PyPI: https://pypi.org/project/skillcheck/1.0.1/ (available after publish)
- GitHub Release: https://github.com/moonrunnerkc/skillcheck/releases/tag/v1.0.1
- agentskills.io specification: https://agentskills.io/specification
- README: https://github.com/moonrunnerkc/skillcheck/blob/main/README.md
