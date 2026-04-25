# skillcheck v1.0.0 Upgrade Plan

**Agent-Native Semantic Reasoning for SKILL.md Governance**

Prepared for Bradley R. Kinnard (moonrunnerkc)
Date: April 24, 2026

---

## 1. Vision & Positioning

**Current state (v0.2.0):** Static linter with frontmatter validation, description scoring (heuristic), token budgets, cross-agent flags, and GitHub Action. 6 organic stars with zero updates since March 12. Solves real pain in a growing ecosystem.

**v1.0 Goal:** Add the missing agent-native semantic reasoning layer that no existing tool provides. When an agent is present, it helps the skill critique and improve itself. When no agent is present, skillcheck falls back to fast symbolic checks. It also maintains a lightweight history of validation runs so you can see how skill quality evolves.

No superlatives. Just clear engineering value.

**Established expertise (from public work):**

- Founder, Aftermath Technologies
- Senior AI Systems Architect: offline-first AI, neurosymbolic systems, RL for autonomous agents
- Creator of swarm-orchestrator (83 stars): evidence-based quality gates + parallel orchestration for Copilot/Claude Code/Codex
- Creator of ruleprobe: verifies whether agents actually follow instruction files
- Public writing: "We Parsed 580 AI Instruction Files. 96% of the Content Can't Be Verified"

skillcheck v1.0 closes the loop: swarm-orchestrator governs agent behavior, ruleprobe verifies instruction adherence, skillcheck ensures the skills themselves are semantically sound and self-verifying.

---

## 2. Competitive Landscape (Honest Assessment)

**What others have (as of April 24, 2026):**

- **agent-ecosystem/skill-validator** (45 stars, active 4 days ago): Excellent symbolic + LLM-as-judge scoring, content quality metrics (imperative ratio, information density, instruction specificity), cross-language contamination detection, Go, Homebrew, pre-commit hooks, GitHub Actions annotations.
- **gh skill** (GitHub CLI, launched April 16 2026): Native provenance tracking via frontmatter (repository, ref, tree SHA), spec validation via `gh skill publish`, immutable releases, content-addressed change detection.
- **agent-skill-linter** (William-Yeh, Python): Spec compliance + auto-fix, semantic rules, CI integration.
- **skills-ref** (agentskills.io official): Reference validation tool from the spec authors.

Symbolic validation (frontmatter, structure, token budgets, basic quality) is largely solved.

**What none of them have (our wedge):**

- True agent-native semantic self-critique with structured, validated reasoning output
- Capability graph extraction that turns a skill into a machine-readable dependency/intent model
- Validation history ledger that shows quality trajectory over time

This is narrow enough to win, broad enough to matter.

---

## 3. Architecture: Two-Mode Design

No waffling. Clean binary:

**Agent Mode** (running inside Claude Code, Cursor, Codex, etc.): Full semantic reasoning via structured self-critique prompts that the calling agent executes and returns as validated JSON. The agent IS the semantic reasoner. Zero external dependencies, zero API keys, zero cost beyond what's already running.

**Standalone Mode** (no agent available): Pure symbolic rules only. Fast, lightweight, zero ML deps. `pip install skillcheck` in under 5 seconds.

### Layer 1: Enhanced Symbolic Engine

All current v0.2.0 rules plus only the gaps not covered by skill-validator: deeper cross-agent compatibility checks, token budget nuance, VS Code silent failure patterns (from the "silently fails in VS Code" research). Every rule carries a source tag (spec, advisory, or cross-agent research) and confidence level.

Don't over-invest here. skill-validator covers this ground well in Go. Our symbolic layer exists to feed the semantic layer and to serve standalone users who want a Python tool.

### Layer 2: Agent-Native Semantic Engine

The differentiator. No existing tool does this.

**Agent Self-Critique Mode (`--agent-reason`):** The calling agent evaluates whether the skill's instructions are clear, complete, and executable from the agent's own perspective. skillcheck emits a structured self-critique prompt, the agent returns a JSON semantic report, skillcheck validates and scores it. The agent validates the instructions it would follow, from inside its own reasoning context.

**Capability Graph Extraction:** Parses the skill into a lightweight directed graph of claimed capabilities, required inputs, and expected outputs. Detects contradictions, missing edges, or over-claims. Direct synergy with ruleprobe's verification model.

**Activation Hypothesis Generator (experimental):** Generates 5-10 high-probability natural-language triggers that would cause different agents to select the skill. Scores discoverability entropy. Ships clearly marked experimental with caveat: each agent's skill selection algorithm is proprietary and changes between versions. These are informed estimates, not guarantees.

### Validation History Ledger

`gh skill` handles install-time provenance (repo, ref, tree SHA). Don't compete with GitHub on supply chain tracking.

skillcheck tracks what GitHub doesn't: validation quality over time. Stored as `.skillcheck-history.json`, append-only:

- Which agents has this skill been validated against?
- What were the semantic alignment scores at each run?
- When was the last passing validation?
- What changed between the last two validations?

This is the "has this skill been proven good?" record, complementing GitHub's "where did this skill come from?" record.

---

## 4. Feature Set

### v1.0 Ships Only These

| Feature | Status | Why It Matters | Effort |
|---------|--------|----------------|--------|
| Agent-native self-critique engine | Core (new) | The killer differentiator. Agent runs structured critique prompts and returns machine-readable reasoning. | High |
| Capability graph extraction | Core (new) | Parses skill into directed graph of capabilities/inputs/outputs. Detects contradictions, gaps, over-claims. | Medium |
| Validation history ledger | Core | Tracks quality trends over time (evidence model). Unique vs GitHub + skill-validator. | Low |
| Activation hypothesis generator | Experimental | Generates likely trigger phrases. Clearly marked experimental with routing caveat. | Medium |
| Enhanced symbolic rules | Tightened | Only gaps not covered by skill-validator. | Low |
| Self as SKILL.md | Yes | `/skillcheck path/to/SKILL.md` works inside agents. | Low |
| Rich reasoning-trace reports | Yes | Markdown + JSON with agent reasoning traces. | Low |

### Cut for Scope

- No 8 new quality gates (skill-validator covers this)
- No full cross-agent matrix rewrite
- No benchmarks/security audit in v1.0 (can add later)
- No cross-agent dialect fidelity score (doesn't map to real failure mode)
- No local ML dependencies (PyTorch is 2GB+, kills CLI adoption)
- No provenance sidecar (gh skill owns this now)

---

## 5. Technical Implementation

### Repo Structure

```
skillcheck/
├── cli.py                   # Single entrypoint
├── core/
│   ├── symbolic.py          # All deterministic rules
│   ├── semantic.py          # Agent-reason bridge (no local ML)
│   ├── graph.py             # Capability graph extraction
│   ├── history.py           # Validation history ledger
│   └── reporter.py          # Markdown + JSON output
├── agents/                  # Self-critique prompt templates
│   ├── claude.py
│   ├── codex.py
│   ├── cursor.py
│   └── base.py              # Generic fallback
├── utils/
├── tests/
├── pyproject.toml
└── action.yml
```

### CLI Interface

```
skillcheck path [--format json|md|agent] [--target-agent all|claude|...] [--semantic] [--agent-reason]
```

- Exit codes: 0 pass, 1 errors, 2 warnings, 3 semantic drift detected
- Config via `skillcheck.toml` or inline flags
- Full backward compatibility with v0.2.0

### Dependencies

- Runtime: PyYAML (already present). No new runtime deps.
- Dev: pytest, ruff, mypy
- Agent-native mode: zero additional deps. Uses whatever agent is already running.

---

## 6. Timeline (Realistic, Solo, 4 Other Active Projects)

### Full scope: 10-11 weeks

| Phase | Weeks | Deliverables |
|-------|-------|-------------|
| 0 | 1-2 | Refactor to two-mode architecture + test suite |
| 1 | 3-5 | Agent-native self-critique engine + JSON schema |
| 2 | 6-8 | Capability graph extraction + validation history |
| 3 | 9-10 | Polish, self-host as SKILL.md, docs, release |
| 4 | 11 | Soft launch + one announcement post |

### Compressed: 6-8 weeks

Cut activation hypothesis generator. Ship v1.0 with self-critique + capability graph + history ledger only. Add activation analysis in v1.1.

**Meta:** Use swarm-orchestrator + ruleprobe to develop and verify skillcheck itself. Dogfood everything.

---

## 7. Ecosystem Evidence

The urgency is real and grounded:

- 30+ agents now support SKILL.md: Claude Code, Codex, Copilot, Cursor, Gemini CLI, Antigravity, Hermes, Roo Code, OpenCode, Kiro, Manus, and others
- Official skill catalogs from Anthropic, OpenAI, GitHub, Google, Microsoft, Vercel, Supabase, Hugging Face, MongoDB, Auth0
- Multiple awesome-lists tracking 1000+ skills (VoltAgent, skillmatic-ai, heilcheng)
- Spring AI brought SKILL.md to the Java ecosystem (January 2026)
- agentskills.io spec at v1.0.0 (updated April 1, 2026)
- GitHub CLI `gh skill` launched April 16, 2026, confirming skills are now a first-class supply chain artifact
- 580 instruction files analyzed, 96% unverifiable (your research)
- swarm-orchestrator at 83 stars proves the market wants proof over promises
- Dachary Carey's ecosystem analysis found 22% of skills fail structural validation, confirming the quality gap

---

## 8. Launch Strategy

- Position alongside swarm-orchestrator: "Now your skills get the same treatment as your code"
- Lead with the `--agent-reason` demo: "Watch an agent validate and improve its own skill in real time"
- Post on X (@KChackerman), dev.to, LinkedIn, r/ClaudeAI
- Submit to awesome-agent-skills lists (VoltAgent, skillmatic-ai, heilcheng)
- Engage agentskills.io community
- Target: 30-50 stars in first month (realistic given narrower differentiation and an established Go competitor with 7x current star count)

---

## 9. Corrections Log (What We Killed and Why)

For transparency, these are features and claims killed from the initial draft:

1. **Provenance artifact scoped to validation history.** `gh skill` (launched April 16 2026) handles install-time provenance natively. We track what GitHub doesn't: validation quality over time.
2. **Cross-agent dialect fidelity score killed.** Agents select skills by description matching, not instruction voice. Feature didn't map to a real failure mode.
3. **Local ML dependencies eliminated.** sentence-transformers pulls PyTorch (2GB+). Committed fully to agent-native semantic analysis. Agent present = semantic mode, agent absent = symbolic only.
4. **Competitive landscape corrected.** skill-validator is at 45 stars with LLM-as-judge scoring, content quality metrics, and active maintenance. The differentiation is narrower than originally stated.
5. **Timeline extended from 6-8 to 10-11 weeks.** Honest estimate for solo work alongside four other active projects. 6-8 option preserved with scope cut.
6. **Star target adjusted from 50-100 to 30-50.** Honest given narrower wedge and established competition.
7. **Marketing language removed.** "Category-defining move" and "the definitive governance layer" replaced with specific technical claims backed by evidence.
8. **8 new quality gates cut.** skill-validator covers this ground. Don't replicate solved problems.
9. **Cross-agent matrix cut.** Out of scope for v1.0. Can revisit when agent routing internals are better documented.
