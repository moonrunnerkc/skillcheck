<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/banner.svg">
  <source media="(prefers-color-scheme: light)" srcset=".github/banner.svg">
  <img alt="skillcheck" src=".github/banner.svg" width="600">
</picture>

<br/>

**Cross-agent skill quality gate for `SKILL.md` files.**<br/>
Validates against the [agentskills.io specification](https://agentskills.io/specification), scores description discoverability, checks file references, and warns about cross-platform compatibility.

<br/>

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab.svg)](https://python.org)
[![PyYAML](https://img.shields.io/badge/deps-PyYAML-yellow.svg)](https://pyyaml.org)
[![Tests](https://img.shields.io/badge/tests-137%20passed-brightgreen.svg)](#testing)

</div>

---

## What It Does

`skillcheck` catches problems in your `SKILL.md` files before they hit production across Claude Code, VS Code/Copilot, OpenAI Codex, Cursor, and other agents:

- **Frontmatter validation** -- required fields, character constraints, length limits, reserved words, first/second-person voice, XML tags, unknown fields
- **Full name spec compliance** -- leading/trailing hyphen checks, consecutive hyphen checks, directory-name matching (required by VS Code or the skill silently fails to load)
- **Description quality scoring** -- scores 0-100 across action verbs, trigger phrases, keyword density, specificity, and length. Agents use descriptions to decide whether to activate a skill. A bad description means the skill never fires
- **File reference validation** -- checks that relative file references in the body actually exist on disk and that reference depth stays within one level of SKILL.md
- **Progressive disclosure budget** -- validates the three-tier token budget (metadata ~100 tokens, body <5000 tokens, resources on demand) and flags bloat patterns like oversized code blocks, large tables, and embedded base64
- **Cross-agent compatibility warnings** -- flags fields that only work in Claude Code (`model`, `disable-model-invocation`, `mode`, `hooks`), notes VS Code directory-name requirements, and marks fields with unverified behavior in Codex and Cursor
- **CI-friendly** -- JSON output, deterministic exit codes, zero config

## Install

```bash
pip install skillcheck
```

Or install from source with dev dependencies:

```bash
pip install -e ".[dev]"
```

## Quick Start

```bash
# Validate a single file
skillcheck path/to/SKILL.md

# Scan a directory recursively for all SKILL.md files
skillcheck skills/

# Machine-readable output for CI pipelines
skillcheck skills/ --format json

# Score description quality with a minimum threshold
skillcheck SKILL.md --min-desc-score 50

# Check compatibility for a specific agent
skillcheck SKILL.md --target-agent vscode --strict-vscode

# Skip checks that need filesystem context (useful in CI)
skillcheck SKILL.md --skip-dirname-check --skip-ref-check
```

## Example Output

```
✔ PASS  skills/deploy/SKILL.md
            · info              description.quality-score  Description quality score: 85/100.

✗ FAIL  skills/pdf-tool/SKILL.md
  line 2  ✗ error    frontmatter.name.directory-mismatch  Name 'pdf-processor' does not match parent directory 'pdf-tool'.
  line 3  ⚠ warning  frontmatter.field.unknown            Unknown field 'author'.
          · info     description.quality-score            Description quality score: 45/100.
                     Suggestions: Start with an action verb; Add trigger phrases.
          · info     compat.claude-only                   Field 'model' is Claude Code-specific.

Checked 2 files: 1 passed, 1 failed, 1 warning
```

## Options

| Flag | Description |
|---|---|
| `--format json` | Machine-readable JSON output |
| `--max-lines N` | Override line-count threshold (default: 500) |
| `--max-tokens N` | Override token-count threshold (default: 8000) |
| `--ignore PREFIX` | Suppress rules matching a prefix (repeatable) |
| `--no-color` | Disable colored output |
| `--skip-dirname-check` | Skip directory-name matching (useful for CI temp paths) |
| `--skip-ref-check` | Skip file reference validation |
| `--min-desc-score N` | Minimum description quality score (0-100); below triggers a warning |
| `--target-agent NAME` | Scope compat checks: `claude`, `vscode`, or `all` (default: `all`) |
| `--strict-vscode` | Promote VS Code compat issues to errors |
| `--version` | Show version |

### Examples

```bash
# Override sizing thresholds
skillcheck skills/ --max-lines 800 --max-tokens 6000

# Suppress specific rule categories
skillcheck SKILL.md --ignore frontmatter.description

# Require description quality above 60
skillcheck SKILL.md --min-desc-score 60

# Check only Claude Code compatibility
skillcheck SKILL.md --target-agent claude

# Strict VS Code mode (name must match directory or exit 1)
skillcheck SKILL.md --strict-vscode

# Pipe-friendly plain output
skillcheck SKILL.md --no-color
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | No errors (warnings and info are allowed) |
| `1` | One or more errors found |
| `2` | Input error (missing file, empty directory) |

## Rules

| Rule ID | Severity | What it checks |
|---|---|---|
| `frontmatter.name.required` | error | `name` field must exist |
| `frontmatter.name.max-length` | error | Name must be 64 characters or fewer |
| `frontmatter.name.invalid-chars` | error | Lowercase, numbers, hyphens only |
| `frontmatter.name.leading-trailing-hyphen` | error | No leading or trailing hyphens |
| `frontmatter.name.consecutive-hyphens` | error | No consecutive hyphens |
| `frontmatter.name.reserved-word` | error | Not a reserved word (`claude`, `anthropic`) |
| `frontmatter.name.directory-mismatch` | error | Name must match parent directory (VS Code requirement) |
| `frontmatter.description.required` | error | `description` field must exist |
| `frontmatter.description.empty` | error | Description must not be blank |
| `frontmatter.description.max-length` | error | Description must be 1024 characters or fewer |
| `frontmatter.description.xml-tags` | error | No XML/HTML tags in description |
| `frontmatter.description.person-voice` | error | No first/second-person pronouns |
| `frontmatter.field.unknown` | warning | Flags fields not in the spec |
| `description.quality-score` | info | Scores description 0-100 for agent discoverability |
| `description.min-score` | warning | Description score below `--min-desc-score` threshold |
| `sizing.body.line-count` | warning | Body exceeds line threshold |
| `sizing.body.token-estimate` | warning | Body exceeds token threshold |
| `disclosure.metadata-budget` | warning | Frontmatter exceeds ~100 token metadata budget |
| `disclosure.body-budget` | warning | Body exceeds 5000 token instruction budget |
| `disclosure.body-bloat` | info | Large code blocks, tables, or base64 in body |
| `references.broken-link` | error | Referenced file does not exist |
| `references.depth-exceeded` | warning | Reference deeper than one level from SKILL.md |
| `compat.claude-only` | info | Field only works in Claude Code |
| `compat.vscode-dirname` | info/error | Name does not match parent directory (VS Code) |
| `compat.unverified` | info | Field behavior unverified in Codex/Cursor |

## Limitations

- Token counts are estimates. The heuristic fallback has ~15% error; install `tiktoken` for ~5% error. Neither matches Claude's exact tokenizer (not publicly available).
- Cross-agent compatibility data for Codex and Cursor is based on available documentation as of early 2026. Fields marked "unverified" may work, may be ignored, or may cause issues. File bugs if you find discrepancies.
- Description quality scoring uses heuristics, not an LLM. It catches common patterns (missing action verbs, no trigger phrases, vague words) but cannot evaluate semantic quality.
- Directory-name matching compares against the immediate parent directory. If your CI clones into a temp path, use `--skip-dirname-check`.
- File reference validation only checks references extractable from markdown link syntax and `source:`/`file:` directives. Arbitrary path strings in prose are not detected.

## Testing

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -v
```

## License

MIT
