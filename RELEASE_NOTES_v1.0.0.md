skillcheck v1.0.0 is the first major release. It adds agent-native semantic self-critique, heuristic capability graph extraction with five structural analyzers, and a per-skill validation history ledger on top of the v0.2.0 symbolic foundation. The tool is designed for two modes: when a calling agent is present it uses that agent for semantic analysis; when no agent is present it runs symbolic checks only. No LLM API keys required. Suitable for CI pipelines, local pre-commit hooks, or agent-loop integration.

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

## Verification

After installing `skillcheck==1.0.0`:

```bash
skillcheck --version
# skillcheck 1.0.0

skillcheck skills/skillcheck/SKILL.md --analyze-graph
# Should exit 0 with no errors and no warnings (only INFO diagnostics)
```

## Links

- PyPI: https://pypi.org/project/skillcheck/1.0.0/ (available after publish)
- GitHub Release: https://github.com/moonrunnerkc/skillcheck/releases/tag/v1.0.0 (available after maintainer creates the release)
- agentskills.io specification: https://agentskills.io/specification
- README: https://github.com/moonrunnerkc/skillcheck/blob/main/README.md
