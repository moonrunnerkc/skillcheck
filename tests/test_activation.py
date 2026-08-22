"""Direct tests for activation hypothesis generation and rendering.

`--activation-hypotheses` was exercised only through subprocess CLI tests, which
the in-process coverage tracer cannot see, so both modules sat near 30% measured
coverage while their behavior went unasserted at the unit level. The scoring,
deduplication, entropy, and the three renderers are pure functions; testing them
directly pins the output shape that the CLI mode depends on.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from skillcheck.core.activation import (
    ActivationHypothesis,
    ActivationReport,
    _clean_phrase,
    _dedupe,
    _entropy,
    _keywords,
    generate_activation_hypotheses,
)
from skillcheck.core.activation_render import (
    render_activation_json,
    render_activation_markdown,
    render_activation_text,
)
from skillcheck.parser import parse


def _skill(tmp_path: Path, *, name: str = "deploy-runner", description: str, body: str = "") -> object:
    path = tmp_path / "SKILL.md"
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return parse(path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_clean_phrase_drops_stopwords_and_lowercases() -> None:
    assert _clean_phrase("Deploys the Service Against Staging") == "deploys service staging"


def test_clean_phrase_drops_tokens_under_three_characters() -> None:
    """_WORD_RE requires three characters, so `md` and `ci` never reach the stopword filter."""
    assert _clean_phrase("Validates a SKILL.md for the CI") == "validates skill"


def test_keywords_rank_by_frequency_then_alphabetically() -> None:
    text = "deploy deploy release release rollback"
    # deploy and release both appear twice; the tie breaks alphabetically.
    assert _keywords(text) == ["deploy", "release", "rollback"]


def test_keywords_skip_short_words_and_stopwords() -> None:
    assert _keywords("the ci of an ok deployment") == ["deployment"]


def test_keywords_respect_the_limit() -> None:
    text = " ".join(f"word{i}" for i in range(20))
    assert len(_keywords(text, limit=5)) == 5


def test_entropy_is_zero_for_a_single_hypothesis() -> None:
    assert _entropy([100]) == 0.0


def test_entropy_is_zero_when_nothing_scored() -> None:
    """Guards the divide-by-zero path when every score is 0."""
    assert _entropy([0, 0]) == 0.0
    assert _entropy([]) == 0.0


def test_entropy_is_maximal_for_a_uniform_split() -> None:
    """Four equally likely triggers carry exactly 2 bits."""
    assert _entropy([25, 25, 25, 25]) == 2.0


def test_entropy_rises_as_scores_even_out() -> None:
    assert _entropy([90, 10]) < _entropy([50, 50])


def test_dedupe_keeps_first_occurrence_and_drops_case_duplicates() -> None:
    hypotheses = [
        ActivationHypothesis(phrase="Deploy the app", score=90, rationale="first"),
        ActivationHypothesis(phrase="deploy the app", score=10, rationale="dupe"),
        ActivationHypothesis(phrase="Roll back", score=50, rationale="second"),
    ]
    kept = _dedupe(hypotheses)
    assert [h.rationale for h in kept] == ["first", "second"]


def test_dedupe_drops_empty_phrases() -> None:
    hypotheses = [
        ActivationHypothesis(phrase="   ", score=10, rationale="blank"),
        ActivationHypothesis(phrase="real", score=10, rationale="kept"),
    ]
    assert [h.rationale for h in _dedupe(hypotheses)] == ["kept"]


# ---------------------------------------------------------------------------
# generate_activation_hypotheses
# ---------------------------------------------------------------------------


def test_report_carries_the_skill_name(tmp_path: Path) -> None:
    skill = _skill(tmp_path, description="Deploys services to staging when a release is cut.")
    report = generate_activation_hypotheses(skill)
    assert report.skill_name == "deploy-runner"


def test_hypotheses_are_scored_and_ordered_high_to_low(tmp_path: Path) -> None:
    skill = _skill(
        tmp_path,
        description="Deploys services to staging when a release is cut.",
        body="## Deploy\n\n## Roll back\n",
    )
    report = generate_activation_hypotheses(skill)
    assert report.hypotheses
    scores = [h.score for h in report.hypotheses]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)


def test_limit_caps_the_number_of_hypotheses(tmp_path: Path) -> None:
    skill = _skill(
        tmp_path,
        description="Deploys, releases, rolls back, audits, and verifies services in staging.",
        body="## Deploy\n## Release\n## Roll back\n## Audit\n## Verify\n",
    )
    assert len(generate_activation_hypotheses(skill, limit=2).hypotheses) <= 2


def test_limit_below_one_is_rejected(tmp_path: Path) -> None:
    skill = _skill(tmp_path, description="Deploys services to staging when a release is cut.")
    with pytest.raises(ValueError):
        generate_activation_hypotheses(skill, limit=0)


def test_entropy_matches_the_reported_scores(tmp_path: Path) -> None:
    skill = _skill(
        tmp_path,
        description="Deploys services to staging when a release is cut.",
        body="## Deploy\n\n## Roll back\n",
    )
    report = generate_activation_hypotheses(skill)
    assert report.entropy == _entropy([h.score for h in report.hypotheses])
    assert not math.isnan(report.entropy)


def test_missing_description_still_produces_a_report(tmp_path: Path) -> None:
    """An unparseable or bare skill must not crash the emit mode."""
    path = tmp_path / "SKILL.md"
    path.write_text("---\nname: bare\n---\n\nBody only.\n", encoding="utf-8")
    report = generate_activation_hypotheses(parse(path))
    assert isinstance(report, ActivationReport)
    assert report.skill_name == "bare"


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


@pytest.fixture
def report(tmp_path: Path) -> ActivationReport:
    skill = _skill(
        tmp_path,
        description="Deploys services to staging when a release is cut.",
        body="## Deploy\n\n## Roll back\n",
    )
    return generate_activation_hypotheses(skill)


def test_text_render_names_the_skill_and_every_phrase(report: ActivationReport) -> None:
    rendered = render_activation_text(report)
    assert report.skill_name in rendered
    for hypothesis in report.hypotheses:
        assert hypothesis.phrase in rendered


def test_markdown_render_is_a_table_with_one_row_per_hypothesis(report: ActivationReport) -> None:
    rendered = render_activation_markdown(report)
    assert rendered.lstrip().startswith("#")
    assert "|" in rendered
    for hypothesis in report.hypotheses:
        assert hypothesis.phrase in rendered


def test_json_render_round_trips(report: ActivationReport) -> None:
    payload = json.loads(render_activation_json(report))
    assert payload["skill_name"] == report.skill_name
    assert payload["entropy"] == report.entropy
    assert len(payload["hypotheses"]) == len(report.hypotheses)
    assert payload["hypotheses"][0]["phrase"] == report.hypotheses[0].phrase


def test_renderers_handle_an_empty_report() -> None:
    """No hypotheses is a valid state; none of the three renderers may crash."""
    empty = ActivationReport(skill_name="bare", entropy=0.0, hypotheses=())
    assert "bare" in render_activation_text(empty)
    assert "bare" in render_activation_markdown(empty)
    assert json.loads(render_activation_json(empty))["hypotheses"] == []
