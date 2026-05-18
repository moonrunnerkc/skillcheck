# skillcheck v1.3 update plan — evaluation and proposal

Status: draft. Author: Brad Kinnard via Claude Opus 4.7 review, 2026-05-18.
Scope: repo state at commit `3c152b7` (post-v1.2.3, `[Unreleased]` `--strict` umbrella).

---

## 1. Where the repo stands today

### What's working

- **Test surface is large and green.** 730 collected, 728 pass + 2 skip, run in ~8s.
  CI matrix covers Linux/macOS/Windows × Python 3.10–3.13.
- **Symbolic core is clean.** Parser, rules/, core/, agents/ separate cleanly; no
  agent module reaches into `cli` or `core/history`. Token estimation has a
  documented heuristic fallback and an opt-in `[tiktoken]` extra.
- **The append-only history ledger already does most of what people would ask
  for.** `check_regression` fires `history.skill.regressed` (WARNING) today when
  a passing run's content hash now fails. Atomic writes via tempfile + rename.
  No PII, safe to commit. Schema version field is in place.
- **Description quality scorer is already 5-dimensional** (action verbs, trigger
  phrases, keyword density, specificity, length) and returns per-dimension
  suggestions. The internal mechanics are good; only the *external* presentation
  is single-number.
- **v1.2.3 already shipped the integration surface that matters**: composite
  GitHub Action, `--format github` for native PR annotations, pre-commit hook,
  v1 moving tag convention.
- **Cross-agent compat is correctly tagged**. Each diagnostic carries
  `source` (`spec`, `advisory`, `heuristic`, `agent`, `history`) and `confidence`.

### Tech debt and friction (concrete)

1. **CLI dispatch is brittle.** `src/skillcheck/cli.py` is 1195 lines and ~150 of
   them are pairwise mutual-exclusion checks between emit modes. Adding a new
   mode is O(N) more print-and-exit branches. The flag table (`_EMIT_FLAGS`)
   appears once but the conflict matrix is open-coded above it.

2. **Documentation drift.** README still documents `--warnings-as-errors` as a
   public flag (README L270, L291, L295), but `[Unreleased]` in CHANGELOG says
   it was removed in favor of `--strict`. CLI still carries it as an internal
   `args.warnings_as_errors` attribute. CHANGELOG says "test count updated to
   701"; README banner says "730 tests"; collection confirms 730. README and
   CHANGELOG diverge on at least three counts.

3. **Dead code from the v1.2.3 action refactor.** `action/entrypoint.py` is no
   longer invoked (composite action now calls `skillcheck` directly with
   `--format github`). The file is kept around as ~150 lines of cruft. The
   CHANGELOG explicitly says it is no longer used.

4. **Stale release notes at repo root.** `RELEASE_NOTES_v1.0.0.md`,
   `RELEASE_NOTES_v1.0.1.md`, `RELEASE_NOTES_v1.1.0.md` — three files duplicating
   the CHANGELOG. Either move to `docs/releases/` or delete.

5. **`--semantic` silently flips `--analyze-graph`.** `cli.py` does
   `if args.semantic and args.ingest_graph is None: args.analyze_graph = True`.
   No mention in the README's `--semantic` row. Hidden coupling that bites
   anyone reading `--help`.

6. **Pre-commit hook entry has no opinion.** `.pre-commit-hooks.yaml` just
   invokes `skillcheck` bare. In a pre-commit context this prints color codes
   into git hook output and inherits whatever `skillcheck.toml` says. A safer
   default would pin `--no-color --format text` or document that the project's
   `skillcheck.toml` is the source of truth.

7. **action.yml floor pin is loose.** `pip install --quiet "skillcheck>=1.0.1"`
   when no version is supplied. `@v1` tag is the intended pin, but the install
   line still floats. Either tighten to `>=1.2,<2` or remove the lower bound
   since the action ref is the real pin.

8. **`python-version: ">=3.10"` in action.yml** — `setup-python` accepts that
   form, but most callers will get whatever's latest. Pinning to `"3.12"` makes
   the action's runtime deterministic without touching what the package itself
   supports.

9. **Description score is opaque from outside.** The 0–100 number is emitted; the
   five dimension contributions are not. Suggestions hint at what's missing but
   not by how much. Authors fixing a low score guess at which lever moves the
   needle.

10. **History regression cannot fail the build today.** The WARNING fires but
    `--strict` is the only knob and it escalates *all* warnings. There's no
    "fail only on regression" gate, which is the targeted CI use case.

11. **Activation hypotheses is flagged experimental** with no graduation
    criteria. Either commit to it or schedule removal.

---

## 2. Response to Grok's proposal

### Where I agree

- **Make description score transparency the flagship**: agree on direction, with
  caveats. The 5-dimension breakdown already exists internally — the change is
  exposing it, not building it. A `--explain-score` flag or always-on per-dim
  breakdown in `--format text` / `--format json` is a 20-line patch. Keep the
  framing honest: the scorer is a heuristic and the README already says so;
  don't oversell it as solving the discoverability problem, just as
  *measuring it transparently*.

- **Regression gate as a unique lane**: agree, but Grok overstates the gap.
  The regression diagnostic exists today (`history.skill.regressed`,
  `check_regression` at `src/skillcheck/core/history.py:194`). The unlocked
  feature is making it *gate* CI — an opt-in `--fail-on-regression` flag that
  escalates only that one rule to exit 1. Five lines of code, not a new
  subsystem.

- **Compat checks as advisory with provenance**: agree. We already tag `source`
  and `confidence` in every diagnostic. The cheap improvement is appending the
  data-source date to compat messages ("verified against Cursor docs
  2026-04-20") so authors can judge staleness without reading the source.

- **Leave the symbolic core untouched**: agree on the core itself. Push back
  below on the CLI dispatch layer.

### Where I disagree or push back

- **Grok ranks features over hygiene.** The most pressing wins aren't new
  features — they're (a) README ↔ CHANGELOG ↔ code reconciliation, (b)
  deleting `action/entrypoint.py` and the three RELEASE_NOTES files, and (c)
  collapsing the CLI emit-mode conflict matrix into a single mode table. None
  of those is glamorous. All of them reduce maintenance load and lower the bar
  for new contributors more than any feature would. They should ship first.

- **Grok proposes positioning skillcheck as "the tool that catches drift."**
  That's accurate but the README repositioning has a cost: every external
  reference to current framing breaks. I'd hold the repositioning until after
  the v1.3 hygiene pass and ship it with the regression gate flag as a unit, so
  the new framing has new evidence behind it.

- **"No other tool tracks quality over time" is a claim that decays.** Grok
  treats it as a defensible moat. Treat it as a current advantage worth
  surfacing, not as a strategic position to defend, because anyone else can
  add a JSON file too.

- **Grok is silent on dead code and doc drift.** Those are the issues that
  actually hurt today's users, not unanswered ecosystem problems. Fix the
  house before adding rooms.

- **One Grok-flagged risk to elevate**: token estimation error in CI. The
  optional `[tiktoken]` extra is documented but the GitHub Action does
  `pip install "skillcheck>=1.0.1"` — no extras. Most CI users run with the
  ~15% heuristic and don't know it. The action should accept a
  `with: tiktoken: true` input that installs `skillcheck[tiktoken]`.

---

## 3. Proposed v1.3 plan

Two layers: a **hygiene pass** that should ship as a single PR, and a
**feature pass** that adds the three things worth adding. No new subsystems,
no abstraction speculation.

### Layer A — hygiene (one PR)

1. **Delete `action/entrypoint.py`.** CHANGELOG already says it's unused.
2. **Move or delete `RELEASE_NOTES_v1.0.0.md`, `v1.0.1.md`, `v1.1.0.md`.**
   CHANGELOG covers them. Keep one canonical history.
3. **Reconcile README with code.**
   - Remove the `--warnings-as-errors` row; document `--strict` as the only
     warning-escalation knob.
   - Update the exit-code section accordingly.
   - Fix any other test-count or version drift.
4. **Drop the internal `args.warnings_as_errors` attribute** in favor of
   reading `args.strict_all` directly at the one place it's used
   (`cli.py:1099`). No public flag change.
5. **Add `--semantic → --analyze-graph` coupling to the `--semantic` help
   string.** Cheaper than removing it.
6. **Pin `python-version: "3.12"` in action.yml** for the install step. The
   package still supports 3.10+; this just pins the runtime in CI.
7. **Tighten the action's pip install** to `skillcheck>=1.2,<2` (or remove
   the floor; the action ref is the authoritative pin).
8. **Refactor CLI mutual-exclusion to a mode table.** One `MODES` list, one
   "selected mode" resolver, one conflict-pair iterator. Net negative LOC.
   No behavior change; existing tests must still pass without modification.

Estimated diff: ~400 LOC removed, ~150 LOC added, no new tests required (all
existing CLI tests already cover the conflict matrix).

### Layer B — features (each its own PR)

1. **`--explain-score` (or default per-dim output for description.quality-score).**
   - In `--format text`, after the score message, print four indented lines:
     `action: 20/25 · trigger: 10/25 · keywords: 15/25 · specificity: 10/15 · length: 7/10`.
   - In `--format json`, add a `breakdown` object to the diagnostic payload.
   - No new logic — `score_description` already computes per-dim points;
     just thread the tuple out instead of summing eagerly.
   - Estimated: ~50 LOC, ~5 new tests.

2. **`--fail-on-regression` flag.**
   - When `--history` is active *and* `history.skill.regressed` fires, exit 1
     (overriding the WARNING-is-clean default) regardless of `--strict`.
   - Independent of `--strict` so users can gate on drift without gating on
     all warnings.
   - Document under "Exit Codes" as an explicit case.
   - Estimated: ~20 LOC, ~3 new tests, one CHANGELOG entry.

3. **Provenance dates on compat diagnostics.**
   - Add a `data_source_date` field to each entry in `rules/compat.py`.
   - Append `(as of YYYY-MM-DD)` to messages.
   - One source-of-truth constant per agent: `_CLAUDE_DATA_DATE`,
     `_VSCODE_DATA_DATE`, `_CURSOR_DATA_DATE`.
   - Build a single CI test that fails if any of those dates is older than 12
     months from the current release date. Cheap rot detector.
   - Estimated: ~30 LOC + 1 test.

4. **Optional: `tiktoken: true` action input.**
   - When set, install `skillcheck[tiktoken]` instead of `skillcheck`.
   - Document the tradeoff in the action README section.
   - Estimated: 4 LOC of bash in action.yml.

### Out of scope for v1.3

- Repositioning the README around "drift detection" as the flagship. Defer to
  v1.4 once the regression gate has real-world traction.
- New rule categories or new agent prompt variants.
- Touching the symbolic core. It is fine.
- Promoting or removing `--activation-hypotheses`. Decide in v1.4.

---

## 4. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| README repositioning loses existing search/links | low-med | Defer to v1.4; keep current framing in v1.3 |
| CLI refactor changes a subtle exit-code path | med | Existing tests cover every conflict pair; require zero test modifications during the refactor |
| Tiktoken extra adds install time in CI | low | Opt-in via input, not default |
| Compat date check becomes a chore | low | Single-test, 12-month tolerance; flips to WARNING, never blocks merges |
| Per-dim score breakdown overwhelms `--format text` | low | Single indented line; one-line breakdown, not five lines |

---

## 5. What I would *not* do

- Don't add a configurable score-weighting system. Five dims, fixed weights, is
  fine. Weighting becomes a tuning surface nobody asked for.
- Don't promote `--analyze-graph` to default. It's WARNING-only today; making
  it default-on quietly raises the warning count for every existing user.
- Don't add an LLM-backed mode that calls Anthropic/OpenAI from skillcheck
  itself. The agent-prompt-out / response-in shape is the whole point of the
  separation; don't break it for convenience.
- Don't introduce a plugin system for custom rules in v1.3. `extension_fields`
  in TOML is enough. Plugins are a 10x-complexity step that should wait for
  real demand.

---

## 6. Definition of done for v1.3

- README has zero references to flags that don't exist in `cli.py`.
- `rg "warnings.as.errors" -i` returns zero matches outside the CHANGELOG's
  historical entries.
- `action/entrypoint.py` is gone; `git log -- action/entrypoint.py` shows the
  removal commit.
- `--explain-score` documented, tested, and shown in the README "Output"
  section with a real example.
- `--fail-on-regression` documented and exercised by at least one CI
  integration test against a synthetic ledger.
- `compat.*` diagnostics include their data-source date in the message body.
- Test count rises by 8–12; no existing test is modified except for snapshot
  expectations on the changed diagnostic messages.
