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
