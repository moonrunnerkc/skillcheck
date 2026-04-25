<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/banner.svg">
  <source media="(prefers-color-scheme: light)" srcset=".github/banner.svg">
  <img alt="skillcheck" src=".github/banner.svg" width="600">
</picture>

<br/>

**Cross-agent skill quality gate for `SKILL.md` files.**

</div>

---

## What This Does

`skillcheck` validates SKILL.md files against the [agentskills.io specification](https://agentskills.io/specification): frontmatter structure, description quality, body size, file references, and cross-agent compatibility. New in v1.0: agent-native semantic self-critique, heuristic capability graph extraction with five structural analyzers, and a per-skill validation history ledger. It does not call any LLM API, execute skill instructions, or modify files.

## Why This Exists

Analysis of 580 AI instruction files found that 96% of their content cannot be verified by any static tool. A separate survey found that 22% of SKILL.md files fail basic structural validation. Skills get written, committed, and published to catalogs; nobody proves they work.

skillcheck addresses both gaps with a two-mode design. When a calling agent is present, it uses that agent for semantic self-critique and capability graph extraction: the agent reads the skill's instructions and reports whether they are clear, complete, and internally consistent. When no agent is present, skillcheck runs symbolic checks only: fast, deterministic, no LLM required. The validation history ledger tracks results across runs so you can see how a skill's health changes as you update it or as skillcheck's rules evolve.

## Install

```bash
pip install skillcheck
```

Requires Python 3.10 or later. For more accurate token estimation (reduces error from roughly 15% to roughly 5%):

```bash
pip install "skillcheck[tiktoken]"
```

## Quick Start

```bash
# Symbolic baseline: frontmatter, sizing, references, cross-agent compat
skillcheck path/to/SKILL.md

# Heuristic graph: adds capability graph analysis to the symbolic report
skillcheck path/to/SKILL.md --analyze-graph

# Agent critique workflow: emit a structured prompt, hand it to your agent, ingest the response
skillcheck path/to/SKILL.md --emit-critique-prompt > prompt.txt
# Run prompt.txt through your agent. Agent returns JSON. Then:
skillcheck path/to/SKILL.md --ingest-critique response.json
```

## Modes

### Symbolic

The default mode. Validates frontmatter fields, description quality score, body line and token count, file references, and cross-agent compatibility. Runs without any agent or network access.

```bash
skillcheck SKILL.md
skillcheck skills/            # recursive scan; finds every file named SKILL.md
skillcheck SKILL.md --format json
```

From the field test on Anthropic's official skills repository (18 skills, `runs/anthropics-corpus/01-symbolic-all.txt`): four of eighteen files failed. `claude-api/SKILL.md` failed with `frontmatter.name.reserved-word` because the name contains the reserved word "claude". `template/SKILL.md` failed with `frontmatter.name.directory-mismatch` (name `template-skill`, directory `template`). Both files look correct on casual inspection.

### Heuristic Graph

Extracts a directed capability graph from heading structure and backtick references in the skill body, then runs five structural analyzers. Graph diagnostics are all WARNING severity; they augment the report without changing the exit code.

```bash
skillcheck SKILL.md --analyze-graph
skillcheck SKILL.md --emit-graph              # print graph only, exit 0
skillcheck SKILL.md --emit-graph --format json
```

Graph nodes: `Capability` (section headings), `Input` (backtick references required by capabilities), `Output` (backtick references produced by capabilities). Analyzers fire on orphaned capabilities with no declared I/O, unused inputs, unproduced outputs, capabilities with no description body, and `allowed-tools` entries not backtick-referenced in the body.

From the field test on `mcp-builder/SKILL.md` (`runs/anthropics-mcp-builder/02-graph-analyze.txt`):

```
   line 18  ⚠ warning  graph.capability.orphaned  Capability 'Understand Modern MCP Design'
                        has no declared inputs or outputs.
   line 32  ⚠ warning  graph.capability.orphaned  Capability 'Study MCP Protocol Documentation'
                        has no declared inputs or outputs.
```

Thirteen of fourteen capability headings in that skill had no declared I/O. That is a signal the skill relies entirely on implicit context rather than declared contracts.

### Agent Critique

skillcheck emits a structured self-critique prompt. The calling agent evaluates the skill's instructions from its own perspective and returns JSON. skillcheck validates the schema, converts findings to diagnostics, and merges them with symbolic results. No LLM API is called by skillcheck itself.

```bash
skillcheck SKILL.md --emit-critique-prompt > prompt.txt
# Hand prompt.txt to your agent. Agent returns JSON. Then:
skillcheck SKILL.md --ingest-critique response.json
skillcheck SKILL.md --ingest-critique -                   # read from stdin
skillcheck SKILL.md --emit-critique-prompt --critique-agent codex > prompt.txt
```

`--critique-agent` selects a framing variant tuned for each platform (claude, codex, cursor). The schema and exit codes are identical across all variants.

From the field test (`runs/anthropics-mcp-builder/04-critique-report.txt`): the symbolic run on `mcp-builder/SKILL.md` passed (exit 0), but the ingested critique returned exit 3 with three `semantic.contradiction.detected` errors. One:

```
✗ error  semantic.contradiction.detected  Contradiction between 'Frontmatter
         description: whether in Python (FastMCP) or Node/TypeScript (MCP SDK)''
         and 'Phase 1.3: Language: TypeScript (high-quality SDK support ...) Plus
         AI models are good at generating TypeScript code'': The description
         presents Python and TypeScript as equal options, while Phase 1.3
         explicitly recommends TypeScript and gives reasons to prefer it; the
         skill never reconciles which the agent should pick by default.
```

This class of finding passes every symbolic check but leaves the executing agent without a decision rule.

### Agent Graph

For skills where prose rather than headings carries the capability semantics, emit a graph extraction prompt, run it through an agent, and ingest the response. skillcheck runs both the heuristic and agent-based analyzers, plus divergence detection between the two graphs.

```bash
skillcheck SKILL.md --emit-graph-prompt > graph_prompt.txt
# Hand graph_prompt.txt to your agent. Agent returns JSON. Then:
skillcheck SKILL.md --ingest-graph graph_response.json
# Combine with agent critique (both run, results merged):
skillcheck SKILL.md --ingest-graph graph_response.json --ingest-critique critique_response.json
```

When an agent graph is ingested alongside a heuristic graph, `graph.contradiction.heuristic_disagreement` fires at ERROR severity for any edge the agent claims between two nodes that both appear in the heuristic graph but that edge is absent heuristically. This catches over-claimed capabilities. Pass `--graph-agent codex` or `--graph-agent cursor` for platform-specific prompt framing.

### History

The per-skill validation ledger is an append-only `.skillcheck-history.json` file stored next to the SKILL.md. Each `--history` run appends one record: timestamp, skillcheck version, a 16-character content hash, which modes ran, which agents were used, and diagnostic counts. No message text, skill body content, or user identifiers are stored. Committing the ledger to git is safe.

```bash
skillcheck SKILL.md --history              # run validation and append a record
skillcheck SKILL.md --show-history
skillcheck SKILL.md --show-history --format json
```

When `--history` is active and the current run fails on content that matched a prior passing run, skillcheck emits `history.skill.regressed` (WARNING). This surfaces rule tightening or new agent findings without requiring manual output comparison.

From the field test (`runs/anthropics-mcp-builder/08-history.txt`):

```
History ledger: SKILL.md
Schema version: 1
Total runs: 1

Run   1  2026-04-25T04:21:03Z  FAIL  exit=3
         version=0.2.0  hash=0f4592dcb53cf2b5
         modes=[symbolic, critique(claude), graph(claude)]
         errors=5 warnings=36 info=4
```

## GitHub Action

Three lines to add skillcheck to any CI pipeline:

```yaml
- uses: moonrunnerkc/skillcheck@v0
  with:
    path: skills/
```

Failures block the PR. Errors and warnings appear as inline diff annotations on the changed files. The workflow run page gets a Markdown summary table. For the complete list of action inputs and outputs, see [`action.yml`](action.yml).

The v1.0 graph and critique modes are available as action inputs. Example with strict VS Code mode and a description quality floor:

```yaml
- uses: moonrunnerkc/skillcheck@v0
  with:
    path: skills/
    strict-vscode: true
    min-desc-score: 60
```

## Output

Text output (default), excerpt from `runs/anthropics-corpus/01-symbolic-all.txt`:

```
✗ FAIL  skills/claude-api/SKILL.md
  line 2  ✗ error    frontmatter.name.reserved-word  Name contains reserved word 'claude': 'claude-api'.
            name: claude-api
  line 4  ⚠ warning  frontmatter.field.unknown       Unknown frontmatter field 'license'.

Checked 18 files: 14 passed, 4 failed, 24 warnings
```

JSON output (`--format json`):

```json
{
  "version": "0.2.0",
  "files_checked": 18,
  "files_passed": 14,
  "files_failed": 4,
  "results": [
    {
      "path": "skills/claude-api/SKILL.md",
      "valid": false,
      "diagnostics": [
        {
          "rule": "frontmatter.name.reserved-word",
          "severity": "error",
          "message": "Name contains reserved word 'claude': 'claude-api'.",
          "line": 2,
          "context": "name: claude-api"
        }
      ]
    }
  ]
}
```

The JSON schema is stable. It will not change in a backward-incompatible way within the 0.x series.

## Options

| Flag | Default | Description |
|---|---|---|
| `--format {text,json}` | `text` | Output format |
| `--max-lines N` | `500` | Override the line-count threshold |
| `--max-tokens N` | `8000` | Override the token-count threshold |
| `--ignore PREFIX` | | Suppress rules matching this prefix; can be repeated |
| `--no-color` | `false` | Disable colored output |
| `-q`, `--quiet` | `false` | Suppress all output; exit code only |
| `--skip-dirname-check` | `false` | Skip directory-name matching (useful for CI temp paths) |
| `--skip-ref-check` | `false` | Skip file reference validation |
| `--min-desc-score N` | | Minimum description quality score (0-100); below this triggers a warning |
| `--target-agent {claude,vscode,all}` | `all` | Scope compatibility checks to a specific agent |
| `--strict-vscode` | `false` | Promote VS Code compatibility issues to errors |
| `--emit-critique-prompt` | `false` | Print agent self-critique prompt to stdout and exit 0 |
| `--ingest-critique PATH` | | Read agent critique JSON from PATH or `-` for stdin; merge with symbolic results |
| `--critique-agent NAME` | `claude` | Prompt variant: `claude`, `codex`, or `cursor`. Requires `--emit-critique-prompt` or `--ingest-critique` |
| `--emit-graph` | `false` | Print the extracted capability graph to stdout and exit 0 |
| `--analyze-graph` | `false` | Run graph analyzers and merge diagnostics into the report |
| `--emit-graph-prompt` | `false` | Print the graph-extraction prompt to stdout and exit 0 |
| `--ingest-graph PATH` | | Read agent graph JSON from PATH or `-` for stdin; run graph analyzers and divergence detection, merge results |
| `--graph-agent NAME` | `claude` | Prompt variant for graph extraction: `claude`, `codex`, or `cursor`. Requires `--emit-graph-prompt` or `--ingest-graph` |
| `--history` | `false` | Append a validation record to `.skillcheck-history.json` next to the skill |
| `--show-history` | `false` | Print the validation ledger and exit 0 |
| `--version` | | Show version and exit |

## Exit Codes

| Code | Meaning | Example invocation |
|---|---|---|
| `0` | No errors; warnings and info are allowed | `skillcheck skills/skillcheck/SKILL.md` |
| `1` | One or more errors found | `skillcheck SKILL.md` when the name is invalid |
| `2` | Input error: missing file or empty directory | `skillcheck path/that/does/not/exist` |
| `3` | Symbolic passed but ingested critique found semantic errors | `skillcheck SKILL.md --ingest-critique response.json` when the agent reported contradictions |

Exit code 1 takes priority over 3 when symbolic errors also exist.

## Rules

For a SKILL.md that passes every rule below, see [skills/skillcheck/SKILL.md](skills/skillcheck/SKILL.md).

Source tags: `spec` rules derive from the agentskills.io specification or agent-specific documentation. `advisory` rules encode best-practice recommendations. `heuristic` rules come from structural analysis of the skill body. `agent` rules fire only when an agent response is ingested and compared against the heuristic baseline. `history` rules fire only when `--history` is active and concern the validation ledger rather than skill content.

| Rule ID | Severity | Source | What it checks |
|---|---|---|---|
| `frontmatter.name.required` | error | spec | `name` field must exist |
| `frontmatter.name.type` | error | advisory | `name` must be a string (catches YAML coercion of `true`, `123`, `null`) |
| `frontmatter.name.max-length` | error | spec | Name must be 64 characters or fewer |
| `frontmatter.name.invalid-chars` | error | spec | Lowercase, numbers, hyphens only |
| `frontmatter.name.leading-trailing-hyphen` | error | spec | No leading or trailing hyphens |
| `frontmatter.name.consecutive-hyphens` | error | spec | No consecutive hyphens |
| `frontmatter.name.reserved-word` | error | advisory | Not a reserved word (`claude`, `anthropic`) |
| `frontmatter.name.directory-mismatch` | error | spec | Name must match parent directory (VS Code requirement) |
| `frontmatter.description.required` | error | spec | `description` field must exist |
| `frontmatter.description.type` | error | advisory | `description` must be a string (catches YAML coercion) |
| `frontmatter.description.empty` | error | spec | Description must not be blank |
| `frontmatter.description.max-length` | error | spec | 1024 character maximum |
| `frontmatter.description.xml-tags` | error | advisory | No XML or HTML tags in description |
| `frontmatter.description.person-voice` | error | advisory | No first or second-person pronouns |
| `frontmatter.field.unknown` | warning | advisory | Field not in the known spec list |
| `frontmatter.yaml-anchors` | warning | advisory | YAML anchors and aliases can silently copy values |
| `description.quality-score` | info | advisory | Scores description 0-100 for agent discoverability |
| `description.min-score` | warning | advisory | Score below `--min-desc-score` threshold |
| `sizing.body.line-count` | warning | spec | File exceeds line threshold |
| `sizing.body.token-estimate` | warning | spec | File exceeds token threshold |
| `disclosure.metadata-budget` | warning | spec | Frontmatter exceeds the recommended ~100-token metadata budget |
| `disclosure.body-budget` | warning | spec | Body exceeds the recommended 5000-token instruction budget |
| `disclosure.body-bloat` | info | advisory | Oversized code blocks, large tables, or embedded base64 in body |
| `references.broken-link` | error | advisory | Referenced file does not exist |
| `references.escape` | error | advisory | Reference resolves outside skill directory (CWE-59) |
| `references.depth-exceeded` | warning | spec | Reference deeper than one level from SKILL.md |
| `compat.claude-only` | info | spec | Field only works in Claude Code |
| `compat.vscode-dirname` | info / error | spec | Name does not match parent directory (VS Code); promotes to error with `--strict-vscode` |
| `compat.unverified` | info | advisory | Field behavior unverified in Codex or Cursor |
| `graph.capability.orphaned` | warning | heuristic | Capability heading has no declared inputs or outputs |
| `graph.input.unused` | warning | heuristic | Body-declared input not required by any capability |
| `graph.output.unproduced` | warning | heuristic | Declared output not produced by any capability |
| `graph.capability.empty_description` | warning | heuristic | Capability heading has no description body |
| `graph.tool.unreferenced` | warning | heuristic | `allowed-tools` entry not backtick-referenced in the body |
| `graph.contradiction.heuristic_disagreement` | error | agent | Agent-claimed edge between two heuristically-known nodes that the heuristic does not confirm; possible over-claim |
| `history.skill.regressed` | warning | history | Skill content matches a prior passing run but currently fails; a rule may have tightened or an agent surfaced a new finding |
| `history.write.failed` | warning | history | Could not write the ledger file; validation exit code unaffected |
| `history.read.failed` | warning | history | Could not read the ledger file; validation continues without regression check |

## Case Study

We ran skillcheck against three corpora: Anthropic's official skills repository (18 skills), the `mcp-builder` skill through the full v1.0 pipeline, and five skills from the uxuiprinciples/agent-skills collection. Full run artifacts: `runs/anthropics-corpus/`, `runs/anthropics-mcp-builder/`, `runs/uxuiprinciples-corpus/`.

The symbolic run of the Anthropic corpus returned four failures from eighteen files (exit 1). All four files look correct on review: two had second-person voice in the description, one used "claude" as part of the name (reserved word per spec), and the template skill had a name/directory mismatch. The deeper finding came from running `mcp-builder` through the critique pipeline: the symbolic run passed (exit 0), but the ingested agent critique returned exit 3 with three `semantic.contradiction.detected` errors. The skill's frontmatter offers Python and TypeScript as equal options; its body unconditionally recommends TypeScript in Phase 1.3. That inconsistency means any agent following the Python path hits an unresolved decision point. No static linter catches it. See [docs/case-study-v1-real-world-runs.md](docs/case-study-v1-real-world-runs.md) for the full breakdown.

See also: [docs/case-study-silent-skill-failure.md](docs/case-study-silent-skill-failure.md) (the v0.2.0 case study: a deploy skill that silently disappeared in VS Code due to a name/directory mismatch).

## Limitations

Token counts are estimates. The heuristic fallback has roughly 15% error; install `tiktoken` for roughly 5% error. Neither matches Claude's exact tokenizer, which is not publicly available.

Cross-agent compatibility data for Codex and Cursor comes from available documentation as of early 2026. Fields marked "unverified" may work, may be silently ignored, or may cause issues depending on agent version. File a bug if you find a discrepancy.

Description quality scoring uses heuristics, not an LLM. It catches structural problems (missing action verbs, no trigger phrases, vague words) but cannot evaluate whether instructions are semantically coherent. Agent critique mode addresses that gap.

The heuristic graph extractor uses heading structure and backtick references as proxies for capability declarations. Skills that express capabilities entirely in prose will produce sparse graphs with many `graph.capability.orphaned` warnings. Agent graph mode (`--emit-graph-prompt` / `--ingest-graph`) addresses this but requires a calling agent.

Agent critique and graph modes validate the agent's JSON response against the expected schema and convert it to diagnostics. skillcheck trusts the agent's reasoning; it does not second-guess findings that pass schema validation. The quality of the output depends on the quality of the calling agent.

Directory-name matching compares against the immediate parent directory. Use `--skip-dirname-check` in CI environments that clone to temp paths.

## Testing

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -q
```

647 tests cover all rule modules, CLI exit codes, graph analyzers, divergence detection, critique parsing, history round-trips, and the full self-host pipeline against `skills/skillcheck/SKILL.md`. Fixtures are in `tests/fixtures/`; every rule has at least one positive and one negative test case.

## Maintainer Notes

After editing `skills/skillcheck/SKILL.md`, regenerate the self-host test fixtures so the integration suite stays pinned to the current graph:

```bash
make regen-self-host-fixtures
```

This runs `scripts/regen_self_host_fixtures.py`, which extracts a fresh heuristic graph and writes it to `tests/fixtures/self_host/graph_clean.json`.

To add a new rule: implement `def check_something(skill: ParsedSkill) -> list[Diagnostic]` in the appropriate module under `src/skillcheck/rules/`, register it in `src/skillcheck/rules/__init__.py`, add at least one positive and one negative fixture, and add a row to the Rules table above. Full conventions are in [`.github/CLAUDE.md`](.github/CLAUDE.md).

## License

MIT. See [LICENSE](LICENSE).
