"""Tests for Feature 2: Description quality scoring."""


from skillcheck.parser import parse
from skillcheck.result import Severity
from skillcheck.rules.description import (
    _ACTION_VERBS,
    _score_action_verbs,
    check_description_quality,
    make_min_score_rule,
    score_description,
)
from tests.conftest import FIXTURES_DIR

# ---------------------------------------------------------------------------
# score_description: scoring ranges
# ---------------------------------------------------------------------------

def test_high_quality_description_scores_above_60():
    desc = (
        "Generates conventional commit messages from staged git diffs, "
        "enforcing semantic versioning conventions. Use this skill whenever "
        "the user needs a commit message, mentions conventional commits, "
        "or has staged changes ready to commit."
    )
    score, suggestions, _ = score_description(desc)
    assert score >= 60, f"Expected >= 60, got {score}. Suggestions: {suggestions}"


def test_low_quality_description_scores_below_40():
    desc = "A thing."
    score, suggestions, _ = score_description(desc)
    assert score < 40, f"Expected < 40, got {score}"
    assert len(suggestions) > 0


def test_empty_description_scores_zero():
    score, suggestions, _ = score_description("")
    assert score == 0


def test_vague_description_penalized():
    desc = "A helpful tool and general utility for various things."
    score, _, _ = score_description(desc)
    # This is vague and should score poorly
    assert score < 40


def test_seamless_and_empowering_are_vague():
    """`seamless` and `empowering` (AI tells from .github/CLAUDE.md) reduce
    the specificity score relative to the same description without them.
    """
    base = "Validates SKILL.md files against agentskills.io specification."
    with_seamless = "Validates SKILL.md files via seamless integration with CI."
    with_empowering = "Validates SKILL.md files with an empowering authoring experience."
    base_score, _, base_bd = score_description(base)
    seamless_score, _, seamless_bd = score_description(with_seamless)
    empowering_score, _, empowering_bd = score_description(with_empowering)
    assert seamless_bd["specificity"] < base_bd["specificity"], (
        f"`seamless` must lower the specificity dimension "
        f"(base={base_bd['specificity']}, with={seamless_bd['specificity']})"
    )
    assert empowering_bd["specificity"] < base_bd["specificity"], (
        f"`empowering` must lower the specificity dimension "
        f"(base={base_bd['specificity']}, with={empowering_bd['specificity']})"
    )


def test_action_verb_at_start_boosts_score():
    desc = "Validates SKILL.md files against the agentskills.io specification."
    score_with_verb, _, _ = score_description(desc)
    desc_no_verb = "A checker for SKILL.md files and specification compliance."
    score_no_verb, _, _ = score_description(desc_no_verb)
    assert score_with_verb > score_no_verb


def test_trigger_phrase_boosts_score():
    base = "Generates commit messages from git diffs."
    with_trigger = base + " Use this skill whenever the user mentions commits."
    score_base, _, _ = score_description(base)
    score_trigger, _, _ = score_description(with_trigger)
    assert score_trigger > score_base


def test_very_short_description_penalized():
    desc = "Lints files."
    score, suggestions, _ = score_description(desc)
    # 11 chars, should get length penalty
    assert any("short" in s.lower() for s in suggestions)


def test_very_long_description_penalized():
    desc = "Deploys applications to production. " * 20  # ~700 chars
    score, suggestions, _ = score_description(desc)
    assert any("long" in s.lower() for s in suggestions)


# ---------------------------------------------------------------------------
# check_description_quality: rule integration
# ---------------------------------------------------------------------------

def test_quality_rule_returns_info_diagnostic():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    diagnostics = check_description_quality(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "description.quality-score"
    assert diagnostics[0].severity == Severity.INFO
    assert "/100" in diagnostics[0].message


def test_quality_rule_skips_missing_description(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: no-desc\n---\nBody.\n")
    skill = parse(f)
    assert check_description_quality(skill) == []


def test_quality_rule_skips_empty_description(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: empty-desc\ndescription:\n---\nBody.\n")
    skill = parse(f)
    assert check_description_quality(skill) == []


# ---------------------------------------------------------------------------
# make_min_score_rule
# ---------------------------------------------------------------------------

def test_min_score_rule_warns_below_threshold():
    rule = make_min_score_rule(80)
    skill = parse(FIXTURES_DIR / "bad_desc_quality.md")
    diagnostics = rule(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "description.min-score"
    assert diagnostics[0].severity == Severity.WARNING
    assert "80" in diagnostics[0].message


def test_min_score_rule_passes_above_threshold():
    rule = make_min_score_rule(10)
    skill = parse(FIXTURES_DIR / "valid_good_desc.md")
    diagnostics = rule(skill)
    assert diagnostics == []


def test_min_score_rule_skips_missing_description(tmp_path):
    rule = make_min_score_rule(50)
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: no-desc\n---\nBody.\n")
    skill = parse(f)
    assert rule(skill) == []


# ---------------------------------------------------------------------------
# Regression: vague-word rubric (audit claim 8)
# ---------------------------------------------------------------------------

def test_comprehensive_alone_does_not_penalize():
    """`comprehensive` is context-dependent, not vague filler. A description
    that uses it once should score the same as the same description without it.
    """
    with_word = (
        "Generates comprehensive Python type stubs from runtime introspection. "
        "Use this skill when the user asks for stub generation."
    )
    without_word = (
        "Generates Python type stubs from runtime introspection. "
        "Use this skill when the user asks for stub generation."
    )
    score_with, _, _ = score_description(with_word)
    score_without, _, _ = score_description(without_word)
    assert score_with == score_without, (
        f"'comprehensive' incurred a penalty: {score_with} vs {score_without}"
    )


def test_third_person_verb_forms_count_via_stem_normalization():
    """3rd-person singular ('analyzes', 'identifies', 'classifies') should
    count as action verbs without being explicitly enumerated.
    """
    base = "Identifies cyclic dependencies in plan graphs."
    score, _, _ = score_description(base)
    assert score >= 30, f"Expected leading verb to register, got {score}"


# ---------------------------------------------------------------------------
# Issue #2: action-verb allowlist expansion (1.0.2)
# ---------------------------------------------------------------------------

def test_newly_added_verbs_all_count_as_action_verbs():
       """Every verb added in the #2 expansion (170 total) must register as an
    action verb when used as the first word of a description.
    Regression: issue #2 -- "Investigate..." was falsely flagged.
       """
       _ORIGINAL = frozenset({
             "generate", "analyze", "validate", "deploy", "process",
             "create", "build", "convert", "extract", "format",
             "monitor", "scan", "parse", "transform", "compile",
             "test", "check", "lint", "run", "execute",
             "fetch", "send", "upload", "download",
             "configure", "set", "update", "install", "remove",
             "detect", "identify", "classify", "score", "rank",
             "summarize", "translate", "encrypt", "decrypt",
             "automate", "scaffold", "provision", "migrate", "sync",
       })
       newly_added = sorted(_ACTION_VERBS - _ORIGINAL)
       # No hardcoded count. It recorded how many verbs the 1.0.2 expansion
       # added and had to be edited every time the list grew, which says
       # nothing about behavior. The loop below is the real assertion, and it
       # now covers every verb in the list rather than a fixed number of them.
       assert newly_added, "the expansion set should not be empty"
       for verb in newly_added:
             score, suggestions = _score_action_verbs(f"{verb.title()} something.")
             assert score >= 20, (
                 f"Verb '{verb}' should count as action verb at start "
                 f"(got score={score}, suggestions={suggestions})"
             )
             assert not any(
                 "action verb" in s.lower() for s in (suggestions or [])
             ), f"Verb '{verb}' triggered false-positive action-verb suggestion"


def test_issue_2_regression_investigate_description():
       """Issue #2: "Investigate failing GitLab CI test jobs..." must NOT trigger
    the "Start the description with an action verb" suggestion.
       """
       desc = (
             "Investigate failing GitLab CI test jobs by fetching traces, "
             "mapping failures to local files, and isolating the smallest "
             "rerun only when needed before proposing a fix. Use when given "
             "a failing GitLab job URL or job ID, especially for "
             "dashboard-api-automation test failures."
       )
       score, suggestions, _ = score_description(desc)
       assert not any(
             "action verb" in s.lower() for s in (suggestions or [])
       ), f'Issue #2 description should not trigger action-verb suggestion: {suggestions}'
       assert score >= 90, f"Expected high score for issue #2 description, got {score}"


def test_ing_form_counts_as_action_verb():
    """Present-participle / gerund forms must register via stem normalization:
    -ing alone ('Validating'), e-drop -ing ('Validating' -> 'validate'),
    and doubled-consonant -ing ('Scanning' -> 'scan').
    """
    for desc in (
        "Validating skills before deployment.",
        "Identifying cyclic dependencies in plan graphs.",
        "Scanning SKILL.md files for compliance.",
        "Generating critique prompts for agent self-review.",
    ):
        score, suggestion = _score_action_verbs(desc)
        assert score >= 20, f"-ing form should score >=20: {desc!r} got {score}"
        assert suggestion is None or "action verb" not in suggestion.lower(), (
            f"-ing form must not trigger action-verb suggestion: {desc!r} -> {suggestion}"
        )


def test_ed_form_counts_as_action_verb():
    """Past-tense / past-participle forms must register: -d ('Validated'),
    -ed ('Worked'), -ied ('Identified'), doubled-consonant -ed ('Scanned').
    """
    for desc in (
        "Validated skills before deployment.",
        "Identified cyclic dependencies in plan graphs.",
        "Scanned SKILL.md files for compliance.",
        "Generated critique prompts for agent self-review.",
        "Used for validating SKILL.md files at lint time.",
    ):
        score, suggestion = _score_action_verbs(desc)
        assert score >= 10, f"-ed form should count as a verb: {desc!r} got {score}"


def test_negative_handles_still_excluded():
       """Handles must NOT count as action verb (deliberate exclusion:
    already in _VAGUE_WORDS)."""
       s, _ = _score_action_verbs("Handles X.")
       assert s != 25 and s != 20, (
             f"'Handles' should not count as action verb, got score={s}"
       )


def test_negative_triggers_still_excluded():
       """Triggers must NOT count as action verb (deliberate exclusion:
    would double-count against trigger-phrase scorer)."""
       s, _ = _score_action_verbs("Triggers X.")
       assert s != 25 and s != 20, (
             f"'Triggers' should not count as action verb, got score={s}"
       )
