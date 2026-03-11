# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-03-11

### Added
- **File reference validation** — parses markdown body for `[text](path)`, `![alt](path)`, and `source:`/`file:`/`include:` directives; verifies referenced files exist on disk; warns when references exceed one directory level from SKILL.md.
- **Progressive disclosure budget** — three-tier token budgeting: metadata/frontmatter at ~100 tokens, body at <5,000 tokens, resources loaded on demand. Flags oversized code blocks (>50 lines), large tables (>20 rows), and embedded base64.
- **Cross-agent compatibility warnings** — flags Claude Code-only fields (`model`, `disable-model-invocation`, `mode`, `hooks`, `agent`, `skills`), notes VS Code directory-name requirements, marks fields with unverified behavior in Codex and Cursor. Full compatibility matrix across four agents.
- **Description quality scoring** — scores 0–100 across action verbs, trigger phrases, keyword density, specificity, and length. `--min-desc-score N` flag to enforce a minimum threshold.
- **VS Code strict mode** — `--strict-vscode` promotes VS Code compatibility issues from INFO to ERROR.
- **Agent-scoped checks** — `--target-agent {claude,vscode,all}` scopes compatibility diagnostics to a specific agent.
- **Skip flags** — `--skip-dirname-check` and `--skip-ref-check` for CI environments where filesystem context is unavailable.
- **GitHub Actions CI workflow** — test matrix across Python 3.10–3.13 on Ubuntu, macOS, and Windows; compile check; package build verification.
- **PEP 561 `py.typed` marker** — enables downstream type-checking for library consumers.
- This changelog.

### Changed
- `KNOWN_FRONTMATTER_FIELDS` expanded to include `model`, `context`, `agent`, `hooks`, `user-invocable`, `disable-model-invocation`, `skills`, `mode`, `tags`, `version`, `author`.
- Token estimation uses a word-run + punctuation-run heuristic (~15% error) with optional `tiktoken` for ~5% error.

## [0.1.0] - 2026-03-10

### Added
- Initial release.
- Frontmatter validation: required fields (`name`, `description`), character constraints, length limits, reserved words, first/second-person voice detection, XML tag rejection, unknown field warnings.
- Name spec compliance: leading/trailing hyphen checks, consecutive hyphen checks, directory-name matching.
- Body sizing: configurable line-count and token-count thresholds.
- CLI with `--format json`, `--max-lines`, `--max-tokens`, `--ignore PREFIX`, `--no-color`, `--version`.
- Deterministic exit codes: 0 (pass), 1 (fail), 2 (input error).
- 137 tests covering all rules and CLI behavior.
