# Hermes execution prompt — skillcheck v1.3

Copy everything between the `BEGIN PROMPT` / `END PROMPT` markers and paste it
into Hermes as a single message. No edits required.

---

## BEGIN PROMPT

You are working in `/Users/brad/projects/skillcheck` on the `skillcheck`
Python package (PyPI-published, cross-agent SKILL.md validator). The repo is a
git checkout on branch `main`. Owner is Brad Kinnard (moonrunnerkc / Aftermath
Technologies Ltd).

Your job is to execute the v1.3 update plan in
`docs/update-plan-v1.3.md` end-to-end without stopping for confirmations.
Make reasonable judgment calls on ambiguity and keep moving. Open the plan
file first and treat its "Definition of done" section as your acceptance
criteria.

### Operating rules

1. **Read `docs/update-plan-v1.3.md` first.** It defines the work, the
   non-goals, and the acceptance criteria. Do not deviate from its "What I
   would not do" list.
2. **No clarifying questions to the user.** Make the call, log the reasoning
   in your final report, continue.
3. **Do not touch the symbolic core** (`src/skillcheck/parser.py`,
   `src/skillcheck/result.py`, `src/skillcheck/rules/*` except where Layer B
   item 3 explicitly requires editing `rules/compat.py`).
4. **Existing tests must continue to pass without modification** except for
   snapshot expectations on diagnostic messages you intentionally changed.
   If a test you didn't intend to change starts failing, fix the code, not
   the test.
5. **Bump the version to `1.3.0`** in `pyproject.toml`, `src/skillcheck/__init__.py`
   (if it carries a `__version__`), and `SKILL.md`. Add a `## [1.3.0]` section
   to `CHANGELOG.md` and move `[Unreleased]` entries into it.
6. **One commit per PR-equivalent unit.** Use these commit boundaries:
   - `chore(v1.3): hygiene pass` — Layer A items 1–8 together
   - `feat(cli): --explain-score breakdown for description quality`
   - `feat(history): --fail-on-regression gate flag`
   - `feat(compat): dated provenance on cross-agent diagnostics`
   - `chore(action): optional tiktoken extra input`
   - `chore: release v1.3.0` (version bumps + changelog)
7. **Do not push, do not open a PR, do not tag.** Stop at local commits and
   leave the working tree clean. The user runs the release commands.
8. **Run the full test suite after every commit.** Command:
   `source .venv/bin/activate && python -m pytest tests/ -q`. If a commit
   leaves tests red, fix forward; do not amend or reset published-style
   history.
9. **No `--no-verify`, no `git push --force`, no `git reset --hard`.**

### Concrete work items (from the plan, expanded)

**Layer A — single commit `chore(v1.3): hygiene pass`:**

- Delete `action/entrypoint.py`. Verify with `git grep entrypoint.py` that no
  other file references it.
- Delete (do not move) `RELEASE_NOTES_v1.0.0.md`, `RELEASE_NOTES_v1.0.1.md`,
  `RELEASE_NOTES_v1.1.0.md` at the repo root. The `CHANGELOG.md` is the
  canonical history.
- Remove the `--warnings-as-errors` row from the README options table.
  Rewrite the README "Exit Codes" section so `--strict` is the only documented
  warning-escalation knob. Search `README.md` for every `warnings.as.errors`
  occurrence and reconcile.
- In `src/skillcheck/cli.py`, delete the public-looking
  `args.warnings_as_errors` indirection. Read `args.strict_all` directly at
  the one site (`cli.py:1099`). Keep the exit-code semantics identical:
  warning-only run + `--strict` → exit 1; warning-only run without
  `--strict` → exit 0.
- Update the `--semantic` flag help string to state that it implies
  `--analyze-graph` when no `--ingest-graph` is supplied.
- In `action.yml`, change `setup-python` to pin `python-version: "3.12"` for
  the install/run step. Leave `pyproject.toml`'s `requires-python = ">=3.10"`
  untouched.
- In `action.yml`, tighten the unpinned install line to
  `pip install --quiet "skillcheck>=1.2,<2"`.
- Refactor the CLI mutual-exclusion block (`cli.py` ~780-900) into a single
  mode table. Pattern: one dict `EMIT_MODES: dict[str, bool]` plus one
  resolver that returns the selected mode and raises on multi-select.
  Replace every individual print-and-`sys.exit(2)` pair with a single
  `_die_on_mode_conflict(args)` call. Net LOC must drop; behavior identical.
  After the refactor, run the suite — every CLI test must pass without edit.

**Layer B item 1 — commit `feat(cli): --explain-score breakdown`:**

- In `src/skillcheck/rules/description.py`, return the per-scorer points from
  `score_description` as a third tuple element (or a small dataclass). Do not
  remove the existing two-tuple return; add a sibling function or extend the
  return shape and update all internal callers.
- Add `--explain-score` to the CLI argument parser. When set, the text
  formatter prints one indented line under each `description.quality-score`
  diagnostic showing the five dimensions: `action: N/25 · trigger: N/25 ·
  keywords: N/25 · specificity: N/15 · length: N/10`.
- For `--format json`, always include the `breakdown` object in the
  diagnostic payload regardless of `--explain-score` (JSON consumers can
  ignore extra fields). Document the new field in the README JSON example.
- Tests: at least five new cases — full-credit, zero-credit, mid-range,
  json-breakdown-present, text-flag-off-suppresses-breakdown.

**Layer B item 2 — commit `feat(history): --fail-on-regression`:**

- Add `--fail-on-regression` flag (default false). When set and `--history`
  is active and `history.skill.regressed` fires, set the final exit code to
  1 even if the run would otherwise have exited 0.
- Independent of `--strict`. Document in `--help` and in the README "Exit
  Codes" section as an explicit case.
- Tests: at least three new cases — flag-set-fires-exit-1,
  flag-set-no-regression-exits-0, flag-unset-regression-warns-exit-0.

**Layer B item 3 — commit `feat(compat): dated provenance`:**

- In `src/skillcheck/rules/compat.py`, add three module-level constants:
  `_CLAUDE_DATA_DATE = "2026-04-20"`, `_VSCODE_DATA_DATE = "2026-04-20"`,
  `_CURSOR_DATA_DATE = "2026-04-20"`. Use the most recent date that matches
  the data each rule already encodes; if you cannot verify, use
  `"2026-04-20"` as a reasonable floor and note the assumption in the commit
  message.
- Append ` (as of YYYY-MM-DD)` to the message of every diagnostic produced
  by this module that encodes platform-specific behavior.
- Add one test `tests/test_compat_data_freshness.py` that asserts all three
  constants are within the last 365 days of `datetime.date.today()`. The
  test must produce a clear "compat data is stale" message on failure.
  This test is allowed to start passing today and intentionally rot to a
  failure later — that is the rot detector working as designed.

**Layer B item 4 — commit `chore(action): tiktoken input`:**

- Add a `tiktoken` input to `action.yml` (default `"false"`).
- When `inputs.tiktoken == "true"`, the install step uses
  `pip install --quiet "skillcheck[tiktoken]>=1.2,<2"` (and respects the
  `version` override).
- Document the input in the README GitHub Action section in one sentence:
  "Set `tiktoken: true` to install the optional tokenizer extra; token
  estimates drop from ~15% error to ~5%."

**Release commit `chore: release v1.3.0`:**

- Bump version in `pyproject.toml`, `src/skillcheck/__init__.py`,
  `SKILL.md`.
- Move `[Unreleased]` entries plus all the new ones into a fresh
  `## [1.3.0] - <today UTC>` section in `CHANGELOG.md`. Re-create an empty
  `[Unreleased]` heading.
- Update the README banner line and the "tests cover all rule modules"
  count to the new test count.
- Do not tag, do not push.

### Evidence requirements (final report)

When done, post a single message to the user with the following sections, in
this order:

1. **One-paragraph summary.** What shipped, what didn't, any deviations.
2. **Acceptance checklist.** Each Definition-of-Done bullet from
   `docs/update-plan-v1.3.md` reproduced verbatim, with `[x]` or `[ ]` and
   a one-line note. Do not invent new bullets.
3. **Test evidence.** Output of
   `source .venv/bin/activate && python -m pytest tests/ -q | tail -5`
   from after the final commit. Include the exact count and time.
4. **Commit log.** Output of `git log --oneline main..HEAD` (or
   equivalent if you worked on `main` directly:
   `git log --oneline -7`).
5. **Diff stats.** Output of `git diff --stat <starting-sha>..HEAD` where
   `<starting-sha>` is whatever `HEAD` pointed at when you started.
6. **Drift checks.** Output of each of these commands, verbatim:
   - `rg -i "warnings.as.errors" README.md CHANGELOG.md src/`
   - `rg "entrypoint.py" -l`
   - `ls RELEASE_NOTES_v* 2>/dev/null || echo "removed"`
   - `source .venv/bin/activate && skillcheck --version`
   - `source .venv/bin/activate && skillcheck --help | grep -E "(explain-score|fail-on-regression|tiktoken)"`
   The first command should match only inside historical CHANGELOG entries.
   The second should return nothing. The third should print `removed`. The
   fourth should print `skillcheck 1.3.0`. The fifth should show both
   `--explain-score` and `--fail-on-regression`.
7. **Deviations and judgment calls.** Anything you decided that the plan
   did not fully specify. Cap at 10 bullets.
8. **What you did not do.** A short list of items deferred or skipped, with
   reason. If everything in the plan shipped, write
   "Nothing deferred; all Layer A and Layer B items completed."

### Stop conditions

You stop only when **all** of the following are true:
- All seven commit-boundary items above are committed.
- The full test suite passes on the final commit.
- The final report has been emitted with all eight evidence sections.

If you hit a genuine blocker (a test that fails for reasons unrelated to
your changes, a tool error you cannot work around), commit progress, then
emit the final report with the blocker described in section 7 and section 8.
Do not silently abandon the run.

## END PROMPT
