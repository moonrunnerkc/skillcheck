<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/banner.svg">
  <source media="(prefers-color-scheme: light)" srcset=".github/banner.svg">
  <img alt="skillcheck" src=".github/banner.svg" width="600">
</picture>

<br/>

<img src="https://img.shields.io/pypi/v/skillcheck?style=flat-square" alt="PyPI version"> <img src="https://img.shields.io/pypi/pyversions/skillcheck?style=flat-square" alt="Python"> <img src="https://img.shields.io/github/actions/workflow/status/moonrunnerkc/skillcheck/ci.yml?style=flat-square" alt="CI status"> <img src="https://img.shields.io/github/license/moonrunnerkc/skillcheck?style=flat-square" alt="License">

</div>

Static analyzer for `SKILL.md` files. Validates frontmatter, body sizing, file references, and cross-agent compatibility against the [agentskills.io specification](https://agentskills.io/specification). No network calls. No LLM API calls. No file mutations.

989 tests cover all rule modules.

## Install

```bash
pip install skillcheck
```

Requires Python 3.10 or later. For more accurate token estimates, install the optional extra:

```bash
pip install "skillcheck[tiktoken]"
```

### Token estimation accuracy

Token counts are estimates, and the sizing rules report them as such.

| Estimator | Average error | Offline |
|---|---:|---|
| Default heuristic (no extra) | ~15% | Yes |
| `skillcheck[tiktoken]`, `cl100k_base` | ~5% | After the first run |
| Naive `chars / 4` (what the default replaces) | ~20% | Yes |

The default counts word runs at 1.3 sub-tokens and punctuation runs at 1.5, measured against mixed YAML, markdown, and code. tiktoken downloads its vocabulary on first use, so it is offline only once that cache is warm; the heuristic never touches the network.

Neither estimator matches Claude's tokenizer, because Anthropic's vocabulary is not published. That is why token-based diagnostics are WARNING severity and line-based ones are not: treat a token figure near its threshold as "check this", not as a verdict. Messages carry the estimate and the threshold (`got 612 tokens`) so you can judge the margin yourself.

## Usage

```bash
skillcheck SKILL.md            # validate one file
skillcheck skills/             # scan a directory for files named SKILL.md
skillcheck SKILL.md --format json
skillcheck --help              # full flag reference
```

Sample output:

```
✔ PASS  skills/claude-api/SKILL.md
  line 2   ⚠ warning  frontmatter.name.reserved-word  Name contains the term 'claude'.
  line 4   · info     frontmatter.field.ecosystem      Field 'license' is ecosystem-common.

Checked 18 files: 18 passed, 0 failed, 29 warnings
```

## GitHub Action

```yaml
- uses: moonrunnerkc/skillcheck@v1
  with:
    path: skills/
```

Diagnostics appear as inline PR annotations. Inputs documented in [`action.yml`](action.yml).

## pre-commit

```yaml
repos:
  - repo: https://github.com/moonrunnerkc/skillcheck
    rev: v1.5.0
    hooks:
      - id: skillcheck
```

The hook passes `--no-color` by default so the captured pre-commit log stays clean. Override or extend with `args:` in your `.pre-commit-config.yaml` (for example, `args: ["--no-color", "--strict"]`).

## What it checks

- **Frontmatter**: required fields, types, name and description length limits, reserved-word collisions.
- **Description quality**: 0-100 score across action verbs, trigger phrases, keywords, specificity, and length.
- **Sizing**: line and token thresholds against the agentskills.io disclosure budgets. Token figures are estimates; see [token estimation accuracy](#token-estimation-accuracy).
- **References**: broken links, escapes outside the skill directory, depth limits.
- **Cross-agent compatibility**: Claude Code, VS Code, Codex, Cursor.
- **Capability graph** (`--analyze-graph`): orphaned capabilities, unused inputs, unproduced outputs, unreferenced tools.
- **History ledger** (`--history`): per-skill append-only JSON file tracking validation results across runs.

## Agent modes

When the calling agent can run a prompt, skillcheck can ingest its response and merge findings into the report:

```bash
skillcheck SKILL.md --emit-critique-prompt > prompt.txt
# hand prompt.txt to the agent, then:
skillcheck SKILL.md --ingest-critique response.json
```

The same flow exists for capability graph extraction (`--emit-graph-prompt` / `--ingest-graph`). Prompt variants are tuned per agent via `--critique-agent` and `--graph-agent` (`claude`, `codex`, `cursor`).

An ingested response describes exactly one skill, so `--ingest-critique` and `--ingest-graph` require a single resolved SKILL.md. Pointing them at a directory that expands to more than one skill exits `2`. Run the ingest once per skill.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | No errors. Warnings alone exit 0 unless `--strict` is set. |
| `1` | One or more errors. Also: warnings with `--strict` (the umbrella `--strict-vscode` / `--strict-cursor` only escalate their own diagnostics; the umbrella additionally escalates any warning-only run). Also: `history.skill.regressed` with `--fail-on-regression`. Also: any ingest parse failure. |
| `2` | Input or argument error (missing path, conflicting flags, malformed input, an ingest flag pointed at more than one skill). |
| `3` | Symbolic checks passed but an ingested critique reported semantic errors. |

When both `1` and `3` would apply, `1` wins so CI consumers see the higher-severity signal.

## Configuration

Defaults live in a `skillcheck.toml` discovered upward from the validated path. Override per invocation with `--config PATH`. Organization-specific frontmatter keys belong under `[frontmatter] extension_fields`. Override the name reserved-word list with `[frontmatter] reserved_words = ["acme", "internal"]` (an empty array reverts to the defaults).

`--ignore PREFIX` suppresses any diagnostic whose rule ID starts with `PREFIX`. The prefix is matched against the full dotted rule ID, so all three levels work: a top-level category (`--ignore sizing`), a category-and-field pair (`--ignore frontmatter.name`), or a fully-qualified rule (`--ignore compat.unverified`). The flag is repeatable.

## Documentation

- [`CONTRIBUTING.md`](CONTRIBUTING.md): testing, maintainer workflows, rule-authoring conventions.
- [`docs/case-study-v1-real-world-runs.md`](docs/case-study-v1-real-world-runs.md): runs against the Anthropic skills corpus.
- [`docs/case-study-silent-skill-failure.md`](docs/case-study-silent-skill-failure.md): VS Code dirname-mismatch incident.
- [`skills/skillcheck/SKILL.md`](skills/skillcheck/SKILL.md): a SKILL.md that passes every rule.

## Releases

Pushing a version tag (`v1.2.3`) runs `.github/workflows/release.yml`, which builds the wheel and sdist, issues a SLSA build provenance attestation via `actions/attest-build-provenance`, and publishes to PyPI through trusted publishing. To verify a release artifact before installing:

```bash
gh attestation verify dist/skillcheck-*.whl --owner moonrunnerkc
```

This confirms the wheel was built by `moonrunnerkc/skillcheck` CI from the source at the tagged commit. Untagged builds (PR and main-branch CI) are not attested or published.

## License

MIT. See [`LICENSE`](LICENSE).
