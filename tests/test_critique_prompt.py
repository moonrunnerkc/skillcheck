"""Tests for SelfCritiquePrompt rendering."""

from __future__ import annotations

from pathlib import Path

from skillcheck.agents.base import SCHEMA_VERSION, SelfCritiquePrompt
from skillcheck.parser import parse

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CRITIQUE_DIR = FIXTURES_DIR / "critique"


def _render(filename: str) -> str:
    skill = parse(CRITIQUE_DIR / filename)
    return SelfCritiquePrompt().render(skill)


# ---------------------------------------------------------------------------
# Content requirements
# ---------------------------------------------------------------------------


def test_render_contains_skill_body() -> None:
    skill = parse(CRITIQUE_DIR / "minimal_valid.md")
    rendered = SelfCritiquePrompt().render(skill)
    assert "Reads a CSV file" in rendered


def test_render_contains_skill_frontmatter() -> None:
    rendered = _render("minimal_valid.md")
    assert "csv-parser" in rendered


def test_render_contains_schema_version() -> None:
    rendered = _render("minimal_valid.md")
    assert f"schema version {SCHEMA_VERSION}" in rendered


def test_render_contains_score_field_names() -> None:
    rendered = _render("minimal_valid.md")
    assert "clarity_score" in rendered
    assert "completeness_score" in rendered
    assert "executability_score" in rendered


def test_render_contains_required_field_names() -> None:
    rendered = _render("minimal_valid.md")
    assert "findings" in rendered
    assert "missing_context" in rendered
    assert "contradictions" in rendered


def test_render_contains_worked_example() -> None:
    rendered = _render("minimal_valid.md")
    # The worked example uses these literal values; check a few.
    assert '"clarity_score": 72' in rendered
    assert "works offline with no external services" in rendered


def test_render_contains_severity_options() -> None:
    rendered = _render("minimal_valid.md")
    assert '"error"' in rendered
    assert '"warning"' in rendered
    assert '"info"' in rendered


def test_render_instructs_json_only_response() -> None:
    rendered = _render("minimal_valid.md")
    assert "only with the JSON object" in rendered
    assert "No preamble" in rendered


# ---------------------------------------------------------------------------
# Multi-section skill
# ---------------------------------------------------------------------------


def test_render_multi_section_contains_section_headings() -> None:
    rendered = _render("multi_section.md")
    assert "When to use" in rendered
    assert "What it produces" in rendered


# ---------------------------------------------------------------------------
# Skill with embedded code blocks
# ---------------------------------------------------------------------------


def test_render_skill_with_code_blocks_contains_code() -> None:
    rendered = _render("with_code_blocks.md")
    assert "SELECT" in rendered
    assert "FROM users" in rendered


# ---------------------------------------------------------------------------
# Determinism and purity
# ---------------------------------------------------------------------------


def test_render_is_deterministic() -> None:
    skill = parse(CRITIQUE_DIR / "minimal_valid.md")
    prompt = SelfCritiquePrompt()
    assert prompt.render(skill) == prompt.render(skill)


def test_render_same_input_same_output_across_instances() -> None:
    skill = parse(CRITIQUE_DIR / "minimal_valid.md")
    a = SelfCritiquePrompt().render(skill)
    b = SelfCritiquePrompt().render(skill)
    assert a == b


def test_render_different_skills_produce_different_prompts() -> None:
    rendered_minimal = _render("minimal_valid.md")
    rendered_multi = _render("multi_section.md")
    assert rendered_minimal != rendered_multi


# ---------------------------------------------------------------------------
# Agent subclasses have correct AGENT_ID and render skill content
# ---------------------------------------------------------------------------


def test_claude_prompt_agent_id() -> None:
    from skillcheck.agents.claude import ClaudePrompt
    assert ClaudePrompt.AGENT_ID == "claude"


def test_codex_prompt_agent_id() -> None:
    from skillcheck.agents.codex import CodexPrompt
    assert CodexPrompt.AGENT_ID == "codex"


def test_cursor_prompt_agent_id() -> None:
    from skillcheck.agents.cursor import CursorPrompt
    assert CursorPrompt.AGENT_ID == "cursor"
