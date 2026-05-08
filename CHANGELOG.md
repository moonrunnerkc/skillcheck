# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `--strict` umbrella flag. Escalates warning-only runs to exit 1 and turns on `--strict-vscode` and `--strict-cursor`. Reserves the `strict-all` config field for future strict rules to opt into automatically.
- `strict` action input (`action.yml`) and `INPUT_STRICT` wiring (`action/entrypoint.py`).
- TOML config: `strict-all = true` is now accepted in `skillcheck.toml`.

### Removed

- `--warnings-as-errors` flag (replaced by `--strict`, which subsumes the same exit-code escalation).

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
