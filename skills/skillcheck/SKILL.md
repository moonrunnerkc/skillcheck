---
name: skillcheck
description: Validates and scores SKILL.md files against the agentskills.io specification; use when linting skills for cross-agent compatibility, description quality, or capability graph structure.
version: "1.4.0"
author: "Brad Kinnard (moonrunnerkc), Aftermath Technologies Ltd"
---

skillcheck is a static analyzer for SKILL.md files. It validates frontmatter structure, scores description discoverability, checks file references, and extracts a capability graph from heading and backtick-reference patterns. Run it before committing a skill, plugging it into CI, or publishing to a skill registry.

## Prerequisites

- path - the SKILL.md file or directory to validate
- prompt.txt - file path for a saved agent prompt (critique or graph extraction)
- response.json - file path for an agent-provided JSON response

## Validate a skill

Pass `path` to `skillcheck` for a full structural check against the agentskills.io specification. Validates name constraints, description quality, body sizing, file references, and cross-agent compatibility. The `validation report` is written to stdout. Exit codes: 0 no errors, 1 errors found, 2 input error (missing file), 3 symbolic passed but semantic critique flagged errors.

```bash
skillcheck <path>
skillcheck <path> --format json
```

## Review a skill with an agent

skillcheck generates a structured critique prompt for `path` and ingests `response.json` as the agent's reply. Save the emitted prompt to `prompt.txt`. The merged `validation report` combines symbolic diagnostics and semantic findings from the critique.

```bash
skillcheck <path> --emit-critique-prompt > prompt.txt
```

Hand `prompt.txt` to your agent. The agent returns JSON. Save the response as `response.json`, then ingest it.

```bash
skillcheck <path> --ingest-critique response.json
```

Pass `--critique-agent codex` or `--critique-agent cursor` to select a prompt variant tuned for that platform. The critique JSON schema is identical across all agent targets.

## Extract a capability graph

skillcheck extracts the `capability graph` from heading structure and backtick references in the body of `path`. Use `prompt.txt` for emitted graph prompts and ingest `response.json` from your agent for richer extraction.

Run graph analysis using the heuristic extractor (no agent needed):

```bash
skillcheck <path> --analyze-graph
```

For richer extraction, emit the graph prompt, run it through your agent, and ingest the response:

```bash
skillcheck <path> --emit-graph-prompt > prompt.txt
skillcheck <path> --ingest-graph response.json
```

Print the graph to stdout:

```bash
skillcheck <path> --emit-graph
skillcheck <path> --emit-graph --format json
```

When both heuristic and agent graphs are available, skillcheck compares them and emits `graph.contradiction.heuristic_disagreement` at error severity for agent-claimed edges that the heuristic does not confirm.

## Check validation history

Append a record to the `validation ledger` for each `--history` run on `path`. The ledger is stored in `.skillcheck-history.json` next to the skill file, is append-only, and is safe to commit.

```bash
skillcheck <path> --history
skillcheck <path> --show-history
skillcheck <path> --show-history --format json
```

Each record stores the timestamp, skillcheck version, a 16-character content hash, which validation modes ran, and diagnostic counts. When the skill content matches a prior passing run but the current run fails, skillcheck emits `history.skill.regressed` to flag rule tightening or a new agent finding.

## Outputs

- validation report - diagnostic output written to stdout
- capability graph - graph of capabilities, inputs, and outputs extracted from the skill body
- validation ledger - written to `.skillcheck-history.json` next to the skill file
