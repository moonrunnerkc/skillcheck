# v1.0 Field Test: Three Corpora, Real Findings

Prepared April 25, 2026. All run artifacts are in `runs/`.

## What We Ran

Three corpora, two validation tiers.

**Anthropic official skills corpus** (18 skills). Cloned from the Anthropic skills repository. Ran symbolic validation only. Full output: `runs/anthropics-corpus/01-symbolic-all.txt`.

**Anthropic mcp-builder skill** (1 skill, full v1.0 pipeline). Repeated symbolic validation, then heuristic graph analysis (`runs/anthropics-mcp-builder/02-graph-analyze.txt`), then agent self-critique with Claude (`runs/anthropics-mcp-builder/04-critique-report.txt`), then agent graph extraction with Claude (`runs/anthropics-mcp-builder/06-graph-agent-report.txt`), then the combined full pipeline (`runs/anthropics-mcp-builder/07-full-pipeline.txt`). History ledger: `runs/anthropics-mcp-builder/08-history.txt`.

**uxuiprinciples/agent-skills** (5 skills). Ran symbolic validation in strict VS Code mode. Full output: `runs/uxuiprinciples-corpus/02-strict-vscode.txt`.

```bash
# Anthropic corpus - symbolic
skillcheck /tmp/anthropics-skills/skills/ --format text

# mcp-builder - full pipeline
skillcheck /tmp/anthropics-skills/skills/mcp-builder/SKILL.md --emit-critique-prompt \
  | <claude> > /tmp/critique-response.json
skillcheck /tmp/anthropics-skills/skills/mcp-builder/SKILL.md \
  --ingest-critique /tmp/critique-response.json \
  --ingest-graph /tmp/graph-response.json \
  --history

# uxuiprinciples - strict VS Code
skillcheck /tmp/uxuiprinciples-skills/ --strict-vscode --format text
```

## What We Found

### Anthropic corpus: four failures from eighteen files

Summary: 14 passed, 4 failed (exit 1).

| File | Rule | Diagnostic |
|---|---|---|
| `canvas-design/SKILL.md` | `frontmatter.description.person-voice` | Description uses second-person voice ('You should') |
| `claude-api/SKILL.md` | `frontmatter.name.reserved-word` | Name contains reserved word 'claude': 'claude-api' |
| `theme-factory/SKILL.md` | `frontmatter.description.person-voice` | Description uses second-person voice ('you can') |
| `template/SKILL.md` | `frontmatter.name.directory-mismatch` | Name 'template-skill' does not match parent directory 'template' |

The `claude-api` failure is worth noting. The skill is named `claude-api` because it wraps the Claude API. That name can't be used without a rename; the spec reserves "claude" unconditionally. The two second-person voice failures are in descriptions that read naturally to a human author but are rejected by the spec's requirement for third-person voice.

All eighteen skills carried `frontmatter.field.unknown` warnings for the `license` field. That field is not in the agentskills.io spec but appears consistently across Anthropic's catalog, which suggests the spec is evolving and the license field may be formalized in a future revision.

Eight of eighteen skills scored below 80 on description quality. The most common suggestion: no action verbs found. Description scoring is a heuristic quality signal, not a blocking rule unless `--min-desc-score` is set.

### mcp-builder: symbolic pass, semantic fail

Symbolic validation: exit 0, one warning (`frontmatter.field.unknown` for the `license` field). The skill looks fine to any linter.

Heuristic graph analysis (`--analyze-graph`): exit 0, thirteen `graph.capability.orphaned` warnings. The skill's thirteen capability headings have no backtick-referenced I/O declarations. All thirteen fired:

```
   line 18  ⚠ warning  graph.capability.orphaned  Capability 'Understand Modern MCP Design'
                        has no declared inputs or outputs.
   line 32  ⚠ warning  graph.capability.orphaned  Capability 'Study MCP Protocol Documentation'
                        has no declared inputs or outputs.
   line 45  ⚠ warning  graph.capability.orphaned  Capability 'Study Framework Documentation'
                        has no declared inputs or outputs.
...
```

This is expected for a phased workflow skill where each phase is a heading. The graph analyzer flags it because the skill relies on implicit sequencing, not declared contracts. It is a signal, not necessarily a defect.

Agent critique (`--ingest-critique`, Claude variant): exit 3. The symbolic run passed, but the critique returned three `semantic.contradiction.detected` errors.

**Contradiction 1** (language stack):

```
✗ error  semantic.contradiction.detected  Contradiction between 'Frontmatter
         description: whether in Python (FastMCP) or Node/TypeScript (MCP SDK)''
         and 'Phase 1.3: Language: TypeScript (high-quality SDK support ...) Plus
         AI models are good at generating TypeScript code'': The description
         presents Python and TypeScript as equal options, while Phase 1.3
         explicitly recommends TypeScript and gives reasons to prefer it; the
         skill never reconciles which the agent should pick by default.
```

An agent following this skill hits an unresolved decision point at Phase 1.3. If it follows the frontmatter and chooses Python, Phase 1.3 tells it TypeScript is better but does not say whether to switch. The result depends on the agent's own tiebreaking logic, which varies by platform and version.

**Contradiction 2** (coverage vs. workflow tools):

```
✗ error  semantic.contradiction.detected  Contradiction between 'Phase 1.1:
         Balance comprehensive API endpoint coverage with specialized workflow
         tools ... When uncertain, prioritize comprehensive API coverage.' and
         'Phase 1.1: Workflow tools can be more convenient for specific tasks,
         while comprehensive coverage gives agents flexibility to compose
         operations.': The section first frames coverage and workflow tools as a
         balance to strike, then resolves the balance unconditionally toward
         coverage, undercutting the earlier 'balance' framing without a decision
         rule.
```

**Contradiction 3** (evaluation question requirements):

```
✗ error  semantic.contradiction.detected  Contradiction between 'Phase 4.3:
         questions must be Complex: Requiring multiple tool calls and deep
         exploration' and 'Phase 4.3: questions must be Verifiable: Single,
         clear answer that can be verified by string comparison and Stable:
         Answer won't change over time': Multi-step exploration of an external
         service typically yields answers that vary with live data, which
         conflicts with the single-string, time-stable verification requirement;
         the skill does not explain how to satisfy both at once.
```

Beyond contradictions, the critique surfaced five `semantic.finding.error` diagnostics and ten `semantic.finding.warning` diagnostics. The most actionable error:

```
✗ error  semantic.finding.error  [Phase 1.3 / Reference Files] All reference
         links are relative paths (./reference/mcp_best_practices.md, ...) but
         the skill never tells the agent how to resolve those paths or that they
         live alongside SKILL.md. State that reference files are sibling files
         in the skill bundle and should be read with the file-reading tool
         relative to SKILL.md's directory.
```

This is a real gap: an agent that loads the skill without also loading the referenced files will fail Phase 1.3 silently with no guidance on how to recover.

Full pipeline result: exit 3, 5 errors (all semantic), 36 warnings, 4 info. No symbolic errors. The skill would ship without a flag in any symbolic-only CI pipeline.

### uxuiprinciples: five clean passes in strict VS Code mode

All five skills passed (exit 0) with `--strict-vscode`. Each carried two unknown field warnings (`homepage`, `env`) and three `compat.unverified` info diagnostics for fields not confirmed in Codex and Cursor. Description scores ranged from 47 to 70; all were below 80.

The `homepage` and `env` fields are used consistently across this collection but are not in the agentskills.io spec. Same pattern as the Anthropic `license` field: community usage outrunning spec formalization.

## Why This Matters for v1.0

The mcp-builder run demonstrates the core v1.0 thesis: symbolic validation is necessary but not sufficient. A skill can pass every structural check and still leave an agent with unresolved contradictions that only surface during execution. Agent critique mode moves contradiction detection to the validation step, before the skill gets loaded in production.

The corpus runs validate a secondary point: the most common symbolic failures (voice violations, reserved-word collisions, name/directory mismatches) are invisible to authors who read their own files. They feel correct. A linter catches them in under a second.

The uxuiprinciples results suggest that description scoring will be the most common quality improvement vector for well-maintained skill collections. Structural issues tend to get fixed; description quality tends to drift because it requires deliberate effort rather than compliance.
