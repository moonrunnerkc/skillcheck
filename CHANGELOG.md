# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `[tool.ruff]` and `[tool.mypy]` configuration in `pyproject.toml`. Ruff lints `src` and `tests` with an explicit `E, F, I, UP, B` selection at line length 127 (`E501` ignored for unavoidable long string literals in JSON fixtures and schema text). Mypy runs `strict` against `src/skillcheck` under `python_version = "3.10"`, with an `ignore_missing_imports` override for the untyped `tiktoken` dependency and the `tomllib` 3.11+ stdlib backport branch. The source was brought clean under both with real annotations, not blanket ignores.
- Test coverage measurement via `pytest-cov` (added to the `dev` extra). `[tool.coverage.run]` and `[tool.coverage.report]` configure the run, and `addopts` in `[tool.pytest.ini_options]` adds `--cov=skillcheck --cov-report=term-missing --cov-fail-under=68`, so the floor is enforced on every local run and in CI (which runs the same `pytest`). The floor sits a few points under the ~72% measured on CPython 3.10 to absorb matrix variance: the CLI modules run in subprocesses the in-process tracer does not see, the `tomllib` vs fallback-parser branch flips between Python 3.10 and 3.11+, and a few tests skip on Windows.

### Changed

- CI `lint` job now enforces `ruff check src tests` and `mypy src/skillcheck` (strict) on every push and pull request, replacing the prior `compileall`-only check. Either tool reporting a finding fails the job.
- `cli.py` split to separate argument wiring from command execution. Parser construction, `skillcheck.toml` application, mode-conflict dispatch, and `main` stay in `cli.py`; the per-mode handlers (emit prompts and graphs, `--show-history`, the default validation pipeline) and the path and ingest IO helpers move to a new `skillcheck.commands` module. `skillcheck.cli:main` and the `skillcheck` console script are unchanged. Pure refactor, no behavior change.

### Fixed

- Non-dict frontmatter (a bare scalar or list between the `---` delimiters) no longer crashes with an `AttributeError` traceback. `parser.parse` now raises `ParseError` naming the actual YAML type and the path, which the validation pipeline renders as a clean `parse.error` diagnostic and exit 1.
- Template detection no longer misreads bracketed acronyms as placeholders. The `[...]` branch of the placeholder pattern was unescaped, so `[ISO]`, `[API]`, and `[CLI]` in a real description matched and silently suppressed the deployment-blocking ERROR checks (`frontmatter.name.directory-mismatch`, `compat.vscode-dirname`, description scoring). The literal three-dot placeholder is now matched exactly.
- `--ingest-critique` and `--ingest-graph` now reject a multi-skill target instead of stamping the first skill's ingested diagnostics onto every file. An agent response describes one skill, so pointing an ingest flag at a directory that resolves to more than one SKILL.md exits `2` with an error naming the flag and the path count.
- A malformed history ledger now raises a clean `LedgerError` instead of an uncaught `TypeError`. `load_ledger` validates that the JSON root is an object, that `runs` is a list, and that each run entry is well-formed, and it now checks the `version` field against `LEDGER_SCHEMA_VERSION` (previously read but never enforced), naming both versions on mismatch. Every failure carries the "delete it and re-run with --history" remediation.
- `--analyze-graph` no longer crashes on a repeated tool. `allowed-tools: [Bash, Bash]` minted two graph nodes with the same content-hash ID, tripping the duplicate-node-ID guard with an uncaught `ValueError`. The heuristic extractor now dedupes tool names before building nodes.
- Emit and re-parse modes no longer surface a traceback on a file that plain validation handles cleanly. `--emit-graph`, `--emit-critique-prompt`, `--emit-graph-prompt`, `--agent-reason`, `--activation-hypotheses`, `--analyze-graph`, `--history`, and the `--ingest-*` first-path re-parse now catch `ParseError`, print the message to stderr, and exit 1. `read_ingest_raw` additionally catches `UnicodeDecodeError`, so a non-UTF-8 ingest response file takes the clean exit-2 path instead of crashing.
- Codex compatibility provenance now carries its own `_CODEX_DATA_DATE` constant instead of borrowing `_CLAUDE_DATA_DATE`. The mislabel was invisible because all three provenance dates were equal; the date reported for Codex is now sourced from and freshness-checked against the Codex constant independently.

### Security

- `action.yml` no longer interpolates user-controlled inputs into the shell script. Every input is passed through an `env:` mapping and referenced as `"$INPUT_*"`, so a crafted input value cannot break out of the `run:` block and execute arbitrary commands. Behavior is otherwise identical.
- Ingested critique and graph responses are treated as untrusted input: strings taken from them (missing-context items, contradiction locations, findings, and graph node names) are stripped of terminal control characters before they reach the human-readable report. A response carrying raw ANSI escapes can no longer forge terminal output (a fake `PASS` line, a cleared screen). Control characters are rendered in a visible backslash-escaped form rather than dropped. The JSON output path is unchanged (`json.dumps` already escapes control characters).
- Ingested responses are size-bounded. A response file or stdin payload over 5 MiB (`MAX_INGEST_BYTES`) is rejected with exit 2 before it is read into memory, and any single response list (findings, missing_context, contradictions, capabilities, inputs, outputs, edges) over 10,000 items (`MAX_INGEST_LIST_ITEMS`) is rejected with a clear error. Both messages name the actual size/count and the cap.

### Changed

- The published JSON Schemas (`critique-v1.json`, `graph-v1.json`) now set `additionalProperties: false` on every object, matching the parsers, which already reject unknown fields. An agent that validates its output against the schema no longer produces responses that pass the schema but fail ingest.
- Release automation moved to a dedicated tag-triggered `release.yml`. It builds the wheel and sdist, verifies the built version matches the tag, attests build provenance, and publishes to PyPI through trusted publishing. The dead attest step in `ci.yml` (gated on tags but on a workflow that never runs on tags) was removed, so the README's provenance claim is now backed by a workflow that actually runs. `CONTRIBUTING.md` documents the one-time PyPI trusted-publishing setup.
- Every third-party GitHub Action is now pinned to a full commit SHA (with a trailing version comment) across all workflows and `action.yml`, replacing floating major-version tags. This closes the supply-chain window where a compromised or force-moved tag could run with the workflows' write permissions.
- `pre-commit` is now part of the `dev` extra, so the two `test_pre_commit.py` end-to-end hook tests actually run in CI instead of silently skipping.
- `make verify-release` actually builds the sdist and wheel now. The old guard used `command -v python3 -c "import build"`, which only resolved the `python3` path and never tested the `build` module, so the build verification was effectively meaningless. The target also gained a drift grep asserting the README's pre-commit `rev:` matches the pyproject version, and the README `rev:` was corrected from `v1.3.0` to `v1.4.0`.
- Internal refactors, no behavior change: the three copies of frontmatter-block extraction (`_frontmatter_block`, `_extract_frontmatter_raw`, `_extract_frontmatter_text`) are deduplicated to the single `frontmatter_common._frontmatter_block`.
- The critique and graph parsers now share `require_field` and `decode_json_or_raise` from `agents/_ingest.py` instead of each carrying its own copy. As a side effect the critique JSON-decode error message adopts the graph parser's wording (exception type and diagnostic content unchanged).

## [1.4.0] - 2026-05-27

### Changed

- README exit-codes table expanded: the `1` row now lists every escalation path (errors, warning-only run with `--strict`, regression with `--fail-on-regression`, ingest parse failure) and includes the `1` > `3` priority note that was previously only in `.github/CLAUDE.md`.
- `CONTRIBUTING.md` documents platform-skipped tests so the next maintainer knows why pass/skip ratios differ across the CI matrix without having to grep the suite.
- CLI mutual-exclusion block refactored to a single `_PAIRWISE_CONFLICTS` table walked by one loop, replacing nine hand-written `if ... and ...:` branches. Exit code 2 and stderr messages are unchanged.
- `--history` now fans out across every target path instead of silently writing only when exactly one path is supplied. Each SKILL.md still gets its own per-skill `.skillcheck-history.json` next to it. `--fail-on-regression` escalates to exit 1 when any target regresses.
- `--show-history` with multiple paths still reads only the first path's ledger (each skill has its own), but the extra paths now produce a stderr warning instead of being silently dropped.
- README Configuration section now documents that `--ignore PREFIX` accepts any dotted rule prefix, not just top-level categories. The worked example shows `--ignore compat.unverified` so users can silence the unverified-field info diagnostics while keeping `compat.claude-only` and `compat.vscode-dirname`.
- `action.yml` install step now prefers the action's own checkout when `inputs.version` is empty and `pyproject.toml` is present at `$GITHUB_ACTION_PATH`. This pins both `uses: moonrunnerkc/skillcheck@<tag>` and `uses: ./` dogfood jobs to the tag's source, closing the previous PyPI/tag drift window. When `inputs.version` is set, the action still installs from PyPI at that pin. The PyPI range install remains as a fallback for environments where the checkout is absent.
- `.pre-commit-hooks.yaml` now passes `--no-color` by default. The captured pre-commit log is plain text instead of carrying ANSI escapes from a TTY-less invocation. Consumers who want color back can override `args:` in their own `.pre-commit-config.yaml`.

### Added

- Build provenance attestations on tagged releases. The CI `package` job now invokes `actions/attest-build-provenance@v1` against the built wheel and sdist when the ref starts with `refs/tags/v`. Consumers can verify with `gh attestation verify dist/skillcheck-*.whl --owner moonrunnerkc` before installing. Documented in the README's new `## Releases` section.
- `.github/workflows/release-notes.yml`: when a GitHub Release is published, the workflow inspects `CHANGELOG.md`'s `[Unreleased]` block and, if it has un-promoted content for the tag, opens a PR against `main` that moves the block under a `[<tag>] - <today>` heading. No-op when `[Unreleased]` is empty or when the developer already promoted by hand.
- `tests/test_agent_prompts_smoke.py`: snapshot tests that pin SHA-256 digests of each rendered prompt (six combinations: critique/graph x claude/codex/cursor) against `tests/fixtures/valid_basic.md`. Catches accidental edits to prompt scaffolding without requiring an oracle for prompt quality.
- Published JSON Schema (Draft 2020-12) files for the agent IO contracts: `src/skillcheck/schemas/critique-v1.json` and `src/skillcheck/schemas/graph-v1.json`. Both ship with the wheel. `skillcheck.agents.SCHEMAS` maps `"critique-v1"` and `"graph-v1"` to the on-disk paths so callers can validate agent responses before invoking `--ingest-critique` or `--ingest-graph`. The schemas mirror the parser-enforced required fields, severity enum, kind enums, and score ranges; `test_published_schemas.py` guards drift between the schema files and the parsers.
- `[frontmatter] reserved_words` config key in `skillcheck.toml`. Replaces the default `('anthropic', 'claude')` reserved-word list that powers `frontmatter.name.reserved-word`. An empty array reverts to the defaults so orgs cannot silently disable the check. Example: `reserved_words = ["acme", "internal"]`.
- `references.broken-link` and `references.depth-exceeded` now also scan HTML anchor tags (`<a href="...">`) and inline backtick spans that contain a directory separator (e.g. `` `scripts/foo.py` ``). The backtick extractor is shared with the capability graph (`skillcheck.core.extract_backtick_refs`) so the two extractors agree on what counts as a path-like token. Fenced code blocks (```` ``` ```` blocks) are stripped before backtick scanning so command samples do not produce false positives, and bare filenames (`report.json` with no directory) are excluded because they are typically output mentions, not references.
- `_VAGUE_WORDS` now includes `seamless` and `empowering`. Both lack a concrete-attribute reading in SKILL.md description context and appear on the project's own AI-tell ban list (`.github/CLAUDE.md`). `robust` and `comprehensive` remain excluded because they can describe concrete attributes when qualified (per the v1.1.0 rubric decision).

### Fixed

- `tokenizer._get_tiktoken_enc` is now thread-safe. The first-init fast path takes a module-level lock and re-checks the cached state, so concurrent callers (e.g. editor plugins running in a worker pool) cannot race on `tiktoken.get_encoding`.
- `_is_action_verb` now recognizes `-ing` and `-ed` inflections, including the e-drop ("validating" -> "validate") and doubled-consonant ("scanning" -> "scan") forms. Descriptions like "Validating skills..." or "Used for..." used to score 0 on the action axis even though the leading word was a clear action verb.
- `--format` error message now lists `github` as a valid choice (`cli.py`). The argparse `choices=` set on the `--format` definition has accepted `github` since v1.2.3, but the post-parse runtime check still printed the pre-v1.2.3 four-value list.

### Removed

- Empty `action/` directory and the stale `compileall ... action` step in `.github/workflows/ci.yml`. The Python entrypoint was deleted in v1.3.0; the empty directory and its CI reference lingered. No shipped behavior change (the compile step was already a no-op against an empty directory).

## [1.3.0] - 2026-05-18

### Added

- `--strict` umbrella flag. Escalates warning-only runs to exit 1 and turns on `--strict-vscode` and `--strict-cursor`. Reserves the `strict-all` config field for future strict rules to opt into automatically.
- `strict` action input (`action.yml`).
- TOML config: `strict-all = true` is now accepted in `skillcheck.toml`.
- `--explain-score` flag. Shows per-dimension breakdown (action, trigger, keywords, specificity, length) under each `description.quality-score` diagnostic in text output. JSON format always includes the `breakdown` object regardless of the flag.
- `--fail-on-regression` flag. With `--history`, promotes `history.skill.regressed` to exit 1. Independent of `--strict`.
- `fail-on-regression` and `explain-score` action inputs in `action.yml`.
- Provenance dates on cross-agent diagnostics. Every `compat.*` rule that encodes platform-specific behavior now includes `(as of YYYY-MM-DD)`.
- `_CLAUDE_DATA_DATE`, `_VSCODE_DATA_DATE`, `_CURSOR_DATA_DATE` constants in `rules/compat.py`.
- `test_compat_data_freshness.py`: staleness tests asserting each date is within 365 days of today.
- `tiktoken` action input in `action.yml`. Set `tiktoken: true` to install `skillcheck[tiktoken]`.
- `score_description()` now returns a 3-tuple `(score, suggestions, breakdown)` with per-dimension point breakdown.

### Changed

- Mutual-exclusion block in CLI refactored: individual print-and-sys.exit(2) pairs replaced by `_EMIT_MODES`/`_AUGMENT_FLAGS` dicts and a single `_die_on_mode_conflict()` resolver. Net LOC reduced; behavior identical.
- `--semantic` flag help string now states that it implies `--analyze-graph` when no `--ingest-graph` is supplied.
- `action.yml` install line tightened from unpinned `skillcheck` to `skillcheck>=1.2,<2`. Python version pinned to `3.12` for the setup-python step.
- README options table: removed `--warnings-as-errors` row; added `--fail-on-regression` and `--explain-score` rows.
- README exit codes section: `--strict` and `--fail-on-regression` are now the only documented warning-escalation knobs.
- README GitHub Action section: added `tiktoken: true` documentation.
- Compat diagnostic messages updated with `(as of YYYY-MM-DD)` provenance suffixes.

### Removed

- `--warnings-as-errors` flag (replaced by `--strict`, which subsumes the same exit-code escalation).
- `action/entrypoint.py` (unused since v1.2.3; the composite action runs skillcheck directly).
- `RELEASE_NOTES_v1.0.0.md`, `RELEASE_NOTES_v1.0.1.md`, `RELEASE_NOTES_v1.1.0.md` (CHANGELOG.md is the canonical history).

## [1.2.3] - 2026-05-07

### Added

- `--format github`: outputs diagnostics as GitHub Actions workflow commands (`::error`, `::warning`, `::notice`) with proper escaping for file, line, and message properties. The GitHub Action now defaults to this format so PR annotations render automatically without a Python entrypoint.
- `.pre-commit-hooks.yaml`: adds a `skillcheck` hook for pre-commit, matching `SKILL.md` files and passing filenames to the CLI.
- `CONTRIBUTING.md`: documents the release convention (immutable patch tags plus a force-updated `v1` moving major tag).
- `tests/__init__.py`: makes the test package importable, fixing `from tests.conftest` in environments where another `tests` package shadows the path.
- `nargs="+"` on the `path` argument: the CLI now accepts multiple paths (required by pre-commit's `pass_filenames` mode). Single-path usage is unchanged.

### Changed

- `action.yml` simplified to a two-step composite action that installs skillcheck via pip and runs it directly. The Python entrypoint (`action/entrypoint.py`) is no longer invoked; `--format github` handles PR annotations natively. The `format` input defaults to `github` (was `json`, which was ignored at runtime).
- README GitHub Action section updated to reflect automatic PR annotations via `--format github`.
- README pre-commit section added with a `.pre-commit-config.yaml` snippet.
- README test count updated to 701.

### Removed

- The Python entrypoint (`action/entrypoint.py`) for annotation parsing and step summary generation is no longer used by the action. The action runs skillcheck directly.

## [1.2.2] - 2026-05-03

### Added

- `compat.cursor-description-block-scalar` rule (INFO by default). Flags `description: >`, `description: >+`, `description: |`, and `description: |+` because Cursor's skills UI renders these as empty. The Cursor-safe form is `description: >-` (folded strip). Closes #1.
- `--strict-cursor` flag promotes the new rule to ERROR and fails the run. Mirrors `--strict-vscode`.
- `cursor` is now a valid `--target-agent` choice; promotes the rule to WARNING when set without `--strict-cursor`.
- `strict-cursor` action input (`action.yml`) and `INPUT_STRICT_CURSOR` wiring (`action/entrypoint.py`).
- TOML config: `strict-cursor = true` is now accepted in `skillcheck.toml`.

### Changed

- `frontmatter.name.required` and `frontmatter.description.required` now append a hint when the missing field appears as a `## name:` or `## description:` markdown heading inside the frontmatter block. Frontmatter keys are YAML, not markdown; the hint nudges authors to drop the `##` prefix. Closes #1.

## [1.2.1] - 2026-05-03

### Fixed

- `description.quality-score` no longer flags verb-led descriptions starting with `investigate`, `diagnose`, `triage`, `troubleshoot`, `examine`, `audit`, `inspect`, `compare`, `capture`, `normalize`, or `refactor`. Expanded `_ACTION_VERBS` from 43 to 170 entries to cover investigation, inspection, search, code-work, output, comparison, logging, and normalization clusters. Closes #2.

## [1.2.0] - 2026-04-29

Backward compatibility: previously-passing skills still pass. Some previously-failing skills now warn instead of error and produce exit code 0 instead of 1.

### Added

- `template.detected` info-level rule and `src/skillcheck/template_detection.py` module.
- `ECOSYSTEM_FIELDS` classification for `license`, `repository`, `homepage`, and `template`.
- Config support for `[frontmatter] extension_fields` in `skillcheck.toml`.

### Changed

- `frontmatter.name.reserved-word` demoted from ERROR to WARNING; source tag changed from `spec` to `advisory`; message rewritten.
- `frontmatter.description.person-voice` demoted from ERROR to WARNING; messages rewritten to acknowledge the heuristic.
- Budget-message phrasing aligned with the spec's "recommended" language across `sizing.*` and `disclosure.*` rules.

### Fixed

- `frontmatter.field.unknown` no longer fires on `license`, `repository`, `homepage`, or `template`; these now produce info-level `frontmatter.field.ecosystem` diagnostics or are silent for user extensions.
- Templates (placeholder content, `template: true` flag, or files under `template/` or `templates/` directories) no longer trigger deployment-blocking checks (`frontmatter.name.directory-mismatch`, `compat.vscode-dirname`, `description.quality-score`).

### Internal

- Renamed `config.KNOWN_FRONTMATTER_FIELDS` to `config.SPEC_FIELDS`.
- New `template.detected` rule wired into `rules/__init__.py`.
- Frontmatter rule implementation split into smaller modules while preserving `skillcheck.rules.frontmatter` imports.
- Root `SKILL.md` restored so `skillcheck SKILL.md` self-validation works from the repository root.
- New fixture set under `tests/fixtures/` covering ecosystem fields, user extensions, template detection, and demoted severities.

## [1.1.0] - 2026-04-28

External audit against v1.0.1 surfaced eight repo defects ranging from documentation drift to a CI-confusing exit-code conflation. v1.1.0 ships fixes for all eight, reverses one v1.0.1 behavior change that turned out wrong, and tightens the description scorer's vague-word rubric. The minor bump is driven by the exit-code semantics change (now distinguishes warning-only from input error) and the new `--warnings-as-errors` flag.

### Behavior change

- Warning-only CLI reports now return exit code 0 by default, reversing v1.0.1's "warnings exit 2" decision. Exit code 2 is now reserved for tool-misuse / input errors (missing path, conflicting flags, empty directory) so CI consumers can distinguish them. Pass `--warnings-as-errors` to escalate warning-only runs to exit code 1 for stricter gates. Errors remain 1; semantic drift remains 3.

### Added

- `--warnings-as-errors` flag: escalate warning-only runs to exit 1 for CI configurations that want warnings to block.
- `scripts/summarize_batch.py` and `tests/test_batch15_summarize.py`: maintainer-facing tool that consumes a directory of skillcheck batch-run artifacts (one directory per repo, one subdirectory per skill, paired `*.json` / `*.txt` reports per phase) and writes `summary.csv` plus `findings.md`. Invoked as `python scripts/summarize_batch.py <batch_dir>`. Not exposed as a console script, not wired into the GitHub Action; the action runs skillcheck against one path, this consumes outputs across many. Documented under Maintainer Notes in the README.
- `tests/test_readme_test_count_claim.py`: parses the README's "N tests cover ..." sentence and asserts it matches `pytest --collect-only`. The next time the suite grows without bumping the README number, CI fails. Closes the recurring drift pattern that v1.0.1 had to correct twice.

### Changed

- `action.yml` install step pins `skillcheck>=1.0.1` so consumers fail loudly on unpublished v1 features instead of silently running v0.2.0.
- Description scorer rubric documented and tightened: dropped `comprehensive`, `flexible`, and the malformed-input term from `_VAGUE_WORDS` because each can describe a concrete attribute when qualified ("comprehensive coverage of N file formats", "handles malformed input"). The inclusion rubric is now documented inline. Verified against `anthropics/skills` (17 SKILL.md files): zero score changes, because none of those skills use the dropped words. The rubric edit is a no-op against the current corpus; the new regression tests are forward-looking guards against scoring drift if the list is ever re-expanded.
- Description scorer verb matching: collapsed `_ACTION_VERBS` from 86 entries (base + 3rd-person duplicates) to 42 base forms. Added `_is_action_verb()` to handle stem normalization across `-s`, `-es`, and `-ies` endings. Adding a new verb now only requires the base form.
- README test count bumped from 663 to 667 to include the drift-guard test, two description-scorer regression tests, and the `--warnings-as-errors` test.
- README field-test citations: replaced seven gitignored `runs/...` path references with the exact `skillcheck` commands needed to reproduce each finding. Readers can now verify the claims without access to private artifacts.
- README exit-code table reflects the new semantics; flag table documents `--warnings-as-errors`.

### Removed

- Top-level `git-commit-crafter` SKILL.md from the repo root. It was unrelated to skillcheck and confused first-time readers; the canonical example lives at `skills/skillcheck/SKILL.md`.
- False `@v0` tag claim from the README. Only `@v0.2.0` was ever pushed; the action-install snippet no longer suggests a tag that does not exist. CHANGELOG entries that referenced `@v0` corrected to `@v0.2.0`.

## [1.0.1] - 2026-04-28

End-to-end verification against `anthropics/skills` surfaced documentation drift in the published v1.0.0 README and a batch of post-tag implementation work that had not been committed. v1.0.1 commits that work, ships the docs corrections, and adds guide-parity flags. Behavior change: warning-only runs now return exit code 2 (was 0).

### Changed
- Warning-only CLI reports now return exit code 2. Exit code 1 remains errors; exit code 3 remains semantic drift. README Exit Codes table row 0 updated to "no errors and no warnings".
- README test count corrected from 653 to 663.
- README JSON-stability promise updated from "0.x series" to "v1.x series".
- README field-test numbers reframed as April 2026 snapshots against `anthropics/skills`, with a note that they will drift as upstream evolves.
- `action.yml` `format` input description clarified: accepted but ignored at runtime; the action always invokes skillcheck with `--format json`.
- Development extras now include `ruff>=0.6`, `mypy>=1.10`, and `types-PyYAML>=6.0`.

### Added
- `--semantic`: guide-compatible shortcut that enables semantic-adjacent validation. In standalone mode it runs heuristic graph analysis; with ingested agent responses it merges those diagnostics.
- `--agent-reason`: guide-compatible agent-workflow shortcut. Emits a combined critique and graph prompt packet so the calling agent can run both reasoning steps and feed JSON back through `--ingest-critique` and `--ingest-graph`.
- `--format md` and `--format agent`: Markdown report output and agent-oriented next-action output.
- `skillcheck.toml` config loading: top-level defaults for format, thresholds, target agent, strict VS Code mode, skip flags, ignored rule prefixes, graph analysis, semantic mode, history, and agent variants.
- Experimental `--activation-hypotheses`: generates likely natural-language routing triggers plus a discoverability entropy score. Routing caveat included in every report.
- Machine-readable diagnostic metadata: JSON diagnostics now include `source` and `confidence` fields.
- GitHub Action inputs for the v1.0 modes: `semantic`, `analyze-graph`, `ingest-critique`, `critique-agent`, `ingest-graph`, `graph-agent`, `history`, `activation-hypotheses`. The action still always emits JSON internally for PR annotations.
- `tests/test_v1_completion.py`: covers `--format md`, `--format agent`, `--agent-reason`, `--semantic` graph enabling, `--activation-hypotheses` JSON, `skillcheck.toml` loading, and source/confidence in JSON output.

## [1.0.0] - 2026-04-25

### Changed
- Rewrote README end-to-end for v1.0 launch audience. New sections: "Why This Exists", "Modes" (five subsections: Symbolic, Heuristic Graph, Agent Critique, Agent Graph, History), "Maintainer Notes". Removed v0.2.0-era feature bullet list and duplicated section prose. Restructured Quick Start to lead with the agent-native workflow. Rebuilt Options table from live `argparse` audit; every flag matches its actual help text and default. Rebuilt Rules table from live rule module audit; added source-tag legend paragraph. Added inline v1.0 case study paragraph (full detail at `docs/case-study-v1-real-world-runs.md`). All cited diagnostics and output excerpts trace verbatim to field-test artifacts in `runs/`.
- Added `docs/case-study-v1-real-world-runs.md`: full breakdown of the pre-3B field test covering 18 Anthropic skills (symbolic), `mcp-builder` through the full v1.0 pipeline (symbolic + heuristic graph + agent critique + agent graph), and 5 uxuiprinciples skills (strict VS Code mode). Documents three `semantic.contradiction.detected` errors on a skill that passed all symbolic checks, five `graph.capability.orphaned` patterns, and the recurring unknown-field pattern (`license`, `homepage`, `env`) across official catalogs.

### Added
- Release prep artifacts: `RELEASE_NOTES_v1.0.0.md`, `LAUNCH_POST_v1.0.md`, `LAUNCH_CHECKLIST.md`.
- `skills/skillcheck/SKILL.md`: skillcheck's own SKILL.md, validating the tool against itself. Passes symbolic, graph, critique, and history validation with zero errors and zero warnings. Serves as the worked example for the Rules table in the README.
- Self-host integration test suite (`tests/test_self_host.py`): confirms the bundled SKILL.md passes symbolic validation, all five graph analyzers, critique ingestion, agent graph ingestion with divergence analysis, full CLI pipeline, history round-trip, and description scoring threshold.
- `scripts/regen_self_host_fixtures.py`: regenerates `tests/fixtures/self_host/graph_clean.json` from the live heuristic graph after skill edits.
- `Makefile` with `regen-self-host-fixtures` target: runs the regen script against `skills/skillcheck/SKILL.md`.
- `--history` flag: appends a validation record to the per-skill `.skillcheck-history.json` ledger next to the SKILL.md file. Off by default; existing invocations see no behavior change. Incompatible with emit modes.
- `--show-history` flag: reads the per-skill ledger and prints it (text or JSON via `--format`), then exits 0. Skips all validation. Incompatible with emit modes and `--history`.
- `history.skill.regressed` WARNING rule: fires when `--history` is active, the skill content hash matches a prior passing run, and the current run fails. Indicates a rule tightened or an agent surfaced a new finding.
- `history.write.failed` WARNING rule: fires when `--history` is active but the ledger file cannot be written. Validation exit code is unaffected.
- `history.read.failed` WARNING rule: fires when `--history` is active but the existing ledger cannot be read. Validation continues without regression check.
- `--emit-graph`: emit mode. Prints the extracted capability graph (text or JSON) to stdout and exits 0. Identifies `Capability`, `Input`, and `Output` nodes plus `requires`/`produces` edges heuristically from heading structure and backtick references. Mutually exclusive with `--analyze-graph`, `--emit-critique-prompt`, and `--ingest-critique`.
- `--analyze-graph`: augment mode. Extracts the capability graph from each file, runs all five graph analyzers, and merges diagnostics into the validation report. Compatible with `--ingest-critique` (both run; results merged per file). Graph WARNINGs do not fail validation or change the exit code.
- Five graph rule checkers (all WARNING severity): `graph.capability.orphaned`, `graph.input.unused`, `graph.output.unproduced`, `graph.capability.empty_description`, `graph.tool.unreferenced`. No double-firing: body inputs and frontmatter tools are handled by separate analyzers.
- `graph_render` module: `render_graph_text` and `render_graph_json` pure rendering functions. JSON output is deterministic (field order follows dataclass declaration).
- `merge_diagnostics` public function in `core.semantic` and `core.__init__`. `merge_critique_diagnostics` is now a thin wrapper; existing callers unchanged.
- `--critique-agent {claude,codex,cursor}`: select the prompt template variant for agent self-critique. Prompt framing is tuned per vendor; the schema, parser, and exit codes are identical across all agents. Requires `--emit-critique-prompt` or `--ingest-critique`. Records the agent name as `critique_source` in JSON output and as a header line in text output. Default: `claude`.
- `--emit-critique-prompt`: print the agent self-critique prompt to stdout and exit 0. Use `--format json` to wrap in `{"prompt": "..."}`. In directory mode, prompts are separated by a delimiter line so downstream tools can split per-skill.
- `--ingest-critique PATH`: read an agent self-critique JSON response from PATH (use `-` for stdin), convert to diagnostics, merge with symbolic results, and emit a unified report.
- Exit code 3: symbolic validation passed but the ingested critique contains semantic errors (contradictions or findings with ERROR severity). Exit code 1 takes priority when symbolic errors exist.
- `--emit-graph-prompt`: print the capability graph extraction prompt to stdout and exit 0. Use `--graph-agent` to select the vendor variant. In directory mode, prompts are separated by the same per-skill delimiter used by `--emit-critique-prompt`.
- `--ingest-graph PATH`: read an agent graph extraction JSON response from PATH (use `-` for stdin), parse it into a `CapabilityGraph` with `source="agent"`, run standard graph analyzers, run divergence analyzers against the heuristic baseline, and merge all diagnostics into the validation report.
- `--graph-agent {claude,codex,cursor}`: select the prompt template variant for graph extraction. Framing is tuned per vendor; the schema, parser, and exit codes are identical across all agents. Requires `--emit-graph-prompt` or `--ingest-graph`. Default: `claude`. Records the agent name as `graph_source` in JSON output and as a header line in text output.
- `graph.contradiction.heuristic_disagreement` (ERROR, source: `agent`): fires when an ingested agent graph claims an edge between two nodes that both appear in the heuristic graph but that edge is absent heuristically. Indicates a possible over-claimed capability. Only active when `--ingest-graph` is used.
- Graph extraction prompt module (`agents.graph_base`, `agents.graph_claude`, `agents.graph_codex`, `agents.graph_cursor`): parallel to the critique prompt module. Claude variant uses XML tags and a full worked example; Codex uses markdown headers and a full worked example; Cursor uses a compact type signature only.

## [0.2.0] - 2026-03-11

### Added
- **GitHub Action**: composite action (`moonrunnerkc/skillcheck@v0.2.0`) with PR annotations, job summary table, and JSON output. All CLI flags exposed as action inputs. Three lines of YAML to add to any CI pipeline.
- **`__main__.py` entry point**: `python -m skillcheck` now works as an alternative to the console script.
- **File reference validation**: parses markdown body for `[text](path)`, `![alt](path)`, and `source:`/`file:`/`include:` directives; verifies referenced files exist on disk; warns when references exceed one directory level from SKILL.md.
- **Progressive disclosure budget**: three-tier token budgeting: metadata/frontmatter at ~100 tokens, body at <5,000 tokens, resources loaded on demand. Flags oversized code blocks (>50 lines), large tables (>20 rows), and embedded base64.
- **Cross-agent compatibility warnings**: flags Claude Code-only fields (`model`, `disable-model-invocation`, `mode`, `hooks`, `agent`, `skills`), notes VS Code directory-name requirements, marks fields with unverified behavior in Codex and Cursor. Full compatibility matrix across four agents.
- **Description quality scoring**: scores 0-100 across action verbs, trigger phrases, keyword density, specificity, and length. `--min-desc-score N` flag to enforce a minimum threshold.
- **VS Code strict mode**: `--strict-vscode` promotes VS Code compatibility issues from INFO to ERROR.
- **Agent-scoped checks**: `--target-agent {claude,vscode,all}` scopes compatibility diagnostics to a specific agent.
- **Skip flags**: `--skip-dirname-check` and `--skip-ref-check` for CI environments where filesystem context is unavailable.
- **`-q`/`--quiet` flag**: suppresses all output; exit code only.
- **YAML type coercion detection**: `frontmatter.name.type` and `frontmatter.description.type` catch when `yaml.safe_load` silently converts bare values like `true`, `123`, or `null` into non-string types. Provides clear fix advice (quote the value).
- **YAML anchor detection**: `frontmatter.yaml-anchors` warns when YAML anchors/aliases silently copy values in frontmatter.
- **Symlink escape detection**: `references.escape` errors when a file reference resolves outside the skill directory (CWE-59).
- **GitHub Actions CI workflow**: test matrix across Python 3.10-3.13 on Ubuntu, macOS, and Windows; compile check; package build verification.
- **PEP 561 `py.typed` marker**: enables downstream type-checking for library consumers.
- **[Case study](docs/case-study-silent-skill-failure.md)**: documented the silent VS Code skill failure caused by name/directory mismatch.
- This changelog.

### Changed
- `KNOWN_FRONTMATTER_FIELDS` expanded to include `model`, `context`, `agent`, `hooks`, `user-invocable`, `disable-model-invocation`, `skills`, `mode`, `tags`, `version`, `author`.
- Token estimation uses a word-run + punctuation-run heuristic (~15% error) with optional `tiktoken` for ~5% error.
- Standardized on `collections.abc.Callable` across all modules (was `typing.Callable` in some).

### Fixed
- `check_reference_depth` emitted duplicate diagnostics for `../../` paths (both depth-exceeded and traverses-above). Changed to `elif` so only the most specific warning fires.
- README Rules table described sizing rules as "Body exceeds..." but the code counts full file lines/tokens. Table now says "File exceeds...".

## [0.1.0] - 2026-03-10

### Added
- Initial release.
- Frontmatter validation: required fields (`name`, `description`), character constraints, length limits, reserved words, first/second-person voice detection, XML tag rejection, unknown field warnings.
- Name spec compliance: leading/trailing hyphen checks, consecutive hyphen checks, directory-name matching.
- Body sizing: configurable line-count and token-count thresholds.
- CLI with `--format json`, `--max-lines`, `--max-tokens`, `--ignore PREFIX`, `--no-color`, `--version`.
- Deterministic exit codes: 0 (pass), 1 (fail), 2 (input error).
- 137 tests covering all rules and initial CLI behavior.
