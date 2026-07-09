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
