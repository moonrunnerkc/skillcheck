---
name: skillcheck
description: Validates SKILL.md files for spec-facing structure, sizing, references, cross-agent compatibility, and agent-authored critique or graph diagnostics.
version: "1.3.0"
author: "Brad Kinnard (moonrunnerkc), Aftermath Technologies Ltd"
---

Use this skill when validating a `SKILL.md` file or a directory of skill files with the `skillcheck` CLI.

## Validate

Run the default symbolic checks:

```bash
skillcheck SKILL.md
skillcheck skills/ --format json
```

The report includes errors, warnings, and info diagnostics. Exit code 0 means no errors. Exit code 1 means at least one error, or warnings with `--strict`, or a regression with `--fail-on-regression`. Exit code 2 means input or argument error. Exit code 3 means symbolic validation passed but ingested agent critique found semantic errors.

## Agent workflows

For semantic self-critique, emit a prompt and ingest the returned JSON:

```bash
skillcheck SKILL.md --emit-critique-prompt > prompt.txt
skillcheck SKILL.md --ingest-critique response.json
```

For capability graph work, use:

```bash
skillcheck SKILL.md --analyze-graph
skillcheck SKILL.md --emit-graph --format json
```

## Configuration

`skillcheck.toml` can set CLI defaults and frontmatter extension fields:

```toml
[frontmatter]
extension_fields = ["my-org-tag", "internal-id"]
```
