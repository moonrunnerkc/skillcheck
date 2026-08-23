"""Patterns added to the description scorer after measuring a real corpus.

Every case here is shaped like a description someone actually shipped, taken
from or modeled on a corpus of 61 installed skills, because the defects being
fixed were invisible to invented examples. Two measurements drove the change:

- Six descriptions scored zero on the action dimension purely because "use" was
  missing from a 170-entry verb list, and "Use when receiving code review
  feedback" is the house style for a whole family of real skills.
- Twelve scored zero on trigger, and not one of the 61 reached the 25-point
  tier. That tier needs two pattern matches and the patterns were near-synonyms
  of a single phrasing, so full credit was unreachable rather than merely rare.

Each added pattern gets a positive case (real phrasing that should now score)
and a negative case (prose that must not earn the same credit). The negatives
matter more: the first attempt at this fixed the false negatives and introduced
false positives, where "A nice helper when using things" scored the same trigger
credit as an explicit "Use when ..." because both contain a gerund after a
preposition.
"""
from __future__ import annotations

import pytest

from skillcheck.config import DESCRIPTION_SCORE_WEIGHTS
from skillcheck.rules.description import (
    _CONTEXTUAL_TRIGGER_PATTERNS,
    _STRONG_TRIGGER_PATTERNS,
    _is_action_verb,
    explain_components,
    score_description,
)


def _dim(desc: str, name: str) -> int:
    return score_description(desc)[2][name]


# ---------------------------------------------------------------------------
# Action verbs added after the corpus measurement
# ---------------------------------------------------------------------------


ADDED_VERBS = [
    "add", "brainstorm", "bundle", "choose", "debug", "design", "dispatch",
    "finish", "guide", "implement", "package", "plan", "receive", "review",
    "solve", "start", "use", "verify", "write",
]


@pytest.mark.parametrize("verb", ADDED_VERBS)
def test_added_verb_registers_in_every_inflection(verb: str) -> None:
    """Stem normalization has to cover each addition, not just the base form."""
    assert _is_action_verb(verb)
    assert _is_action_verb(verb.title())
    assert _is_action_verb(verb + "s")


def test_use_opener_no_longer_scores_zero_on_action() -> None:
    """The exact shape of six real descriptions that scored zero before.

    Positive case for adding "use".
    """
    desc = "Use when receiving code review feedback, before implementing suggestions."
    assert _dim(desc, "action") == DESCRIPTION_SCORE_WEIGHTS["action"]


def test_review_and_implement_count_as_actions() -> None:
    desc = "Reviews pull requests and implements the agreed changes on a branch."
    assert _dim(desc, "action") == DESCRIPTION_SCORE_WEIGHTS["action"]


def test_vague_directives_are_still_not_action_verbs() -> None:
    """Negative case. "help", "support", and "provide" name no observable action.

    Adding them would have been the easy way to close the same gap, and would
    have credited descriptions that say nothing about what the skill does.
    """
    for word in ("help", "helps", "support", "supports", "provide", "provides"):
        assert not _is_action_verb(word), word
    assert _dim("Provides support and helps with things.", "action") == 0


def test_handle_and_trigger_remain_excluded() -> None:
    """The pre-existing exclusions survived the expansion.

    "handles" is vague filler scored elsewhere, and "trigger" would double count
    against the trigger dimension.
    """
    for word in ("handle", "handles", "trigger", "triggers"):
        assert not _is_action_verb(word), word


# ---------------------------------------------------------------------------
# Strong trigger forms
# ---------------------------------------------------------------------------


STRONG_POSITIVES = [
    # The single most common opener in the corpus, which matched nothing before:
    # every prior pattern required "use" as an active verb directly before "when".
    'This skill should be used when the user asks to "create a slash command".',
    "Used when a release candidate is promoted to staging.",
    # "whenever the user asks" was covered; plain "when the user asks" was not.
    "Generates release notes when the user requests a changelog for a tag.",
    "Extracts traces when asked to diagnose a failing CI job.",
]


@pytest.mark.parametrize("desc", STRONG_POSITIVES)
def test_strong_trigger_form_is_recognized(desc: str) -> None:
    assert any(p.search(desc) for p in _STRONG_TRIGGER_PATTERNS), desc
    assert _dim(desc, "trigger") >= 20


def test_canonical_opener_now_reaches_full_trigger_credit() -> None:
    """The 25-point tier was unreachable across all 61 corpus descriptions."""
    desc = 'This skill should be used when the user asks to "package an MCP server".'
    assert _dim(desc, "trigger") == DESCRIPTION_SCORE_WEIGHTS["trigger"]


def test_prose_about_users_is_not_a_trigger() -> None:
    """Negative case. Mentioning users is not stating an activation condition."""
    desc = "A catalog of user preferences and the settings each user can change."
    assert not any(p.search(desc) for p in _STRONG_TRIGGER_PATTERNS), desc
    assert _dim(desc, "trigger") == 0


# ---------------------------------------------------------------------------
# Contextual trigger forms, and why they are worth less
# ---------------------------------------------------------------------------


CONTEXTUAL_POSITIVES = [
    "Guidance for distinctive visual design when building new UI.",
    "Validates SKILL.md files when linting a skill directory.",
    "Checks the plan before implementing any change to the schema.",
    "Summarizes the diff after merging a pull request into main.",
]


@pytest.mark.parametrize("desc", CONTEXTUAL_POSITIVES)
def test_contextual_trigger_earns_partial_credit(desc: str) -> None:
    """Real activation context, stated without an imperative."""
    assert any(p.search(desc) for p in _CONTEXTUAL_TRIGGER_PATTERNS), desc
    assert _dim(desc, "trigger") == 15


INCIDENTAL_GERUNDS = [
    "A nice helper when using things.",
    "Generic utility, use before running anything.",
    "Basic tool that is good after installing it.",
]


@pytest.mark.parametrize("desc", INCIDENTAL_GERUNDS)
def test_incidental_gerund_does_not_earn_explicit_trigger_credit(desc: str) -> None:
    """Negative case, and the reason the tiers exist.

    A single tier gave these the same 20 points as a real "Use when ..." opener,
    because a gerund after a preposition is what ordinary prose looks like.
    """
    assert _dim(desc, "trigger") == 15
    assert _dim(desc, "trigger") < _dim(
        "Use this skill when the user asks to lint a skill directory.", "trigger"
    )


def test_two_contextual_forms_do_not_beat_one_explicit_form() -> None:
    """Stacking weak signals must not reach the explicit tier's ceiling."""
    contextual_only = "Runs when scanning and stops before writing."
    explicit = "Use when the user asks to scan a repository."
    assert _dim(contextual_only, "trigger") <= _dim(explicit, "trigger")


def test_scorer_still_separates_good_descriptions_from_filler() -> None:
    """The whole point: the added patterns must not collapse the range."""
    filler = "A simple helper tool for various stuff."
    real = "Use when receiving code review feedback, before implementing suggestions."
    assert score_description(filler)[0] < 40
    assert score_description(real)[0] >= 90


# ---------------------------------------------------------------------------
# --explain-score reports which pattern matched or failed
# ---------------------------------------------------------------------------


def test_every_dimension_is_explained() -> None:
    explained = explain_components("Use when the user asks to lint a skill directory.")
    assert set(explained) == set(DESCRIPTION_SCORE_WEIGHTS)


def test_explanation_names_the_matched_action_verb() -> None:
    explained = explain_components("Validates SKILL.md files when linting a directory.")
    assert "Validates" in explained["action"]


def test_explanation_names_the_matched_trigger_text() -> None:
    explained = explain_components("Use when the user asks to lint a skill directory.")
    assert "explicit trigger" in explained["trigger"]
    assert "Use when" in explained["trigger"]


def test_explanation_distinguishes_contextual_from_explicit() -> None:
    explained = explain_components("Validates SKILL.md files when linting a directory.")
    assert "contextual trigger" in explained["trigger"]
    assert "no explicit form" in explained["trigger"]


def test_explanation_reports_a_failure_when_nothing_matched() -> None:
    explained = explain_components("A simple helper tool for various stuff.")
    assert "no action verb matched" in explained["action"]
    assert "no trigger form matched" in explained["trigger"]


def test_explanation_lists_the_vague_words_it_penalized() -> None:
    explained = explain_components("A simple helper tool for various stuff.")
    for word in ("helper", "simple", "stuff", "tool", "various"):
        assert word in explained["specificity"]
