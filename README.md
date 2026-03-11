<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/banner.svg">
  <source media="(prefers-color-scheme: light)" srcset=".github/banner.svg">
  <img alt="skillcheck" src=".github/banner.svg" width="600">
</picture>

<br/>

**Static analyzer for Claude Code `SKILL.md` files.**<br/>
Validates frontmatter structure and body sizing against the Anthropic skill specification.

<br/>

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab.svg)](https://python.org)
[![PyYAML](https://img.shields.io/badge/deps-PyYAML-yellow.svg)](https://pyyaml.org)
[![Tests](https://img.shields.io/badge/tests-73%20passed-brightgreen.svg)](#testing)

</div>

---

## What It Does

`skillcheck` catches problems in your `SKILL.md` files before they hit production:

- **Frontmatter validation** — required fields, character constraints, length limits, reserved words, first/second-person voice, XML tags, unknown fields
- **Body sizing** — line count and token estimate warnings to keep skills within context-window budgets
- **CI-friendly** — JSON output, deterministic exit codes, zero config

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
```

## Example Output

```
✔ PASS  skills/deploy.md

✗ FAIL  skills/pdf-tool.md
  line 2  ✗ error    frontmatter.name.invalid-chars  Name contains uppercase chars
  line 3  ⚠ warning  frontmatter.field.unknown       Unknown field 'author'

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
| `--version` | Show version |

### Examples

```bash
# Override sizing thresholds
skillcheck skills/ --max-lines 800 --max-tokens 6000

# Suppress specific rule categories
skillcheck SKILL.md --ignore frontmatter.description

# Pipe-friendly plain output
skillcheck SKILL.md --no-color
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | No errors (warnings are allowed) |
| `1` | One or more errors found |
| `2` | Input error (missing file, empty directory) |

## Rules

| Rule ID | Severity | What it checks |
|---|---|---|
| `frontmatter.name.required` | error | `name` field must exist |
| `frontmatter.name.max-length` | error | Name ≤ 64 characters |
| `frontmatter.name.invalid-chars` | error | Lowercase, numbers, hyphens only |
| `frontmatter.name.reserved` | error | Not a reserved word (`claude`, `anthropic`, …) |
| `frontmatter.description.required` | error | `description` field must exist |
| `frontmatter.description.empty` | error | Description must not be blank |
| `frontmatter.description.max-length` | error | Description ≤ 1024 characters |
| `frontmatter.description.xml-tags` | error | No XML/HTML tags in description |
| `frontmatter.description.person-voice` | error | No first/second-person pronouns |
| `frontmatter.field.unknown` | warning | Flags fields not in the spec |
| `sizing.body.line-count` | warning | Body exceeds line threshold |
| `sizing.body.token-estimate` | warning | Body exceeds token threshold |

## Testing

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -v
```

## License

MIT
