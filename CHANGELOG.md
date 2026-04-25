# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

## [1.0.0] - 2026-04-25

### Changed
- Rewrote README end-to-end for v1.0 launch audience. New sections: "Why This Exists", "Modes" (five subsections: Symbolic, Heuristic Graph, Agent Critique, Agent Graph, History), "Maintainer Notes". Removed v0.2.0-era feature bullet list and duplicated section prose. Restructured Quick Start to lead with the agent-native workflow. Rebuilt Options table from live `argparse` audit; every flag matches its actual help text and default. Rebuilt Rules table from live rule module audit; added source-tag legend paragraph. Added inline v1.0 case study paragraph (full detail at `docs/case-study-v1-real-world-runs.md`). All cited diagnostics and output excerpts trace verbatim to field-test artifacts in `runs/`.
- Added `docs/case-study-v1-real-world-runs.md`: full breakdown of the pre-3B field test covering 18 Anthropic skills (symbolic), `mcp-builder` through the full v1.0 pipeline (symbolic + heuristic graph + agent critique + agent graph), and 5 uxuiprinciples skills (strict VS Code mode). Documents three `semantic.contradiction.detected` errors on a skill that passed all symbolic checks, five `graph.capability.orphaned` patterns, and the recurring unknown-field pattern (`license`, `homepage`, `env`) across official catalogs.

### Added
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
- **GitHub Action**: composite action (`moonrunnerkc/skillcheck@v0`) with PR annotations, job summary table, and JSON output. All CLI flags exposed as action inputs. Three lines of YAML to add to any CI pipeline.
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
