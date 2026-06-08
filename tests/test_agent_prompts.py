"""Tests for agent-specific prompt variants and the get_agent_prompt factory."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillcheck.agents import AGENTS, get_agent_prompt
from skillcheck.agents.base import worked_example
from skillcheck.agents.claude import ClaudePrompt
from skillcheck.agents.codex import CodexPrompt
from skillcheck.agents.cursor import CursorPrompt
from skillcheck.agents.parser import parse_critique_response
from skillcheck.parser import parse

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CRITIQUE_DIR = FIXTURES_DIR / "critique"


def _skill():
    return parse(CRITIQUE_DIR / "minimal_valid.md")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_agents_registry_contains_all_variants() -> None:
    assert set(AGENTS.keys()) == {"claude", "codex", "cursor"}


def test_get_agent_prompt_returns_claude_by_default() -> None:
    prompt = get_agent_prompt("claude")
    assert isinstance(prompt, ClaudePrompt)


def test_get_agent_prompt_returns_codex() -> None:
    assert isinstance(get_agent_prompt("codex"), CodexPrompt)


def test_get_agent_prompt_returns_cursor() -> None:
    assert isinstance(get_agent_prompt("cursor"), CursorPrompt)


def test_get_agent_prompt_unknown_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown critique agent") as exc_info:
        get_agent_prompt("gpt-4o")
    msg = str(exc_info.value)
    assert "gpt-4o" in msg
    # Valid IDs must be listed in the error message.
    assert "claude" in msg
    assert "codex" in msg
    assert "cursor" in msg


def test_all_agent_ids_match_registry_keys() -> None:
    for key, cls in AGENTS.items():
        assert cls.AGENT_ID == key


# ---------------------------------------------------------------------------
# Claude prompt structure
# ---------------------------------------------------------------------------


def test_claude_render_contains_xml_skill_tag() -> None:
    rendered = ClaudePrompt().render(_skill())
    assert "<skill_to_critique>" in rendered
    assert "</skill_to_critique>" in rendered


def test_claude_render_contains_xml_schema_tag() -> None:
    rendered = ClaudePrompt().render(_skill())
    assert "<response_schema>" in rendered
    assert "</response_schema>" in rendered


def test_claude_render_contains_worked_example_tag() -> None:
    rendered = ClaudePrompt().render(_skill())
    assert "<worked_example>" in rendered


def test_claude_render_contains_skill_body() -> None:
    skill = _skill()
    rendered = ClaudePrompt().render(skill)
    assert "Reads a CSV file" in rendered


def test_claude_render_no_markdown_headers() -> None:
    rendered = ClaudePrompt().render(_skill())
    assert "### " not in rendered


# ---------------------------------------------------------------------------
# Codex prompt structure
# ---------------------------------------------------------------------------


def test_codex_render_contains_markdown_schema_header() -> None:
    rendered = CodexPrompt().render(_skill())
    assert "### Schema" in rendered


def test_codex_render_contains_markdown_skill_header() -> None:
    rendered = CodexPrompt().render(_skill())
    assert "### Skill" in rendered


def test_codex_render_no_xml_tags() -> None:
    rendered = CodexPrompt().render(_skill())
    assert "<skill_to_critique>" not in rendered
    assert "<response_schema>" not in rendered


def test_codex_render_instructs_json_only() -> None:
    rendered = CodexPrompt().render(_skill())
    assert "Output only the JSON object" in rendered


def test_codex_render_contains_skill_body() -> None:
    skill = _skill()
    rendered = CodexPrompt().render(skill)
    assert "Reads a CSV file" in rendered


# ---------------------------------------------------------------------------
# Cursor prompt structure
# ---------------------------------------------------------------------------


def test_cursor_render_contains_skill_body() -> None:
    skill = _skill()
    rendered = CursorPrompt().render(skill)
    assert "Reads a CSV file" in rendered


def test_cursor_render_no_xml_tags() -> None:
    rendered = CursorPrompt().render(_skill())
    assert "<skill_to_critique>" not in rendered
    assert "<response_schema>" not in rendered


def test_cursor_render_no_markdown_section_headers() -> None:
    # Cursor uses compact_schema_signature, not full schema with ### headers.
    rendered = CursorPrompt().render(_skill())
    assert "### Schema" not in rendered


def test_cursor_render_shorter_than_claude() -> None:
    skill = _skill()
    claude_len = len(ClaudePrompt().render(skill))
    cursor_len = len(CursorPrompt().render(skill))
    # Cursor omits the worked example and uses a compact schema; expect at
    # least 25% fewer characters.
    assert cursor_len < claude_len * 0.75


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_all_renders_are_deterministic() -> None:
    skill = _skill()
    for cls in (ClaudePrompt, CodexPrompt, CursorPrompt):
        p = cls()
        assert p.render(skill) == p.render(skill)


def test_same_agent_different_instances_produce_identical_output() -> None:
    skill = _skill()
    for cls in (ClaudePrompt, CodexPrompt, CursorPrompt):
        assert cls().render(skill) == cls().render(skill)


def test_different_agents_produce_different_output() -> None:
    skill = _skill()
    renders = [cls().render(skill) for cls in (ClaudePrompt, CodexPrompt, CursorPrompt)]
    # All three must be distinct.
    assert len(set(renders)) == 3


# ---------------------------------------------------------------------------
# Worked example parseable by parse_critique_response
# ---------------------------------------------------------------------------


def test_worked_example_is_valid_critique_json() -> None:
    # worked_example() is embedded in claude/codex prompts; it must be parseable.

    # Extract just the JSON object from the worked example.
    example_text = worked_example()
    # The example body is a raw JSON object.
    critique = parse_critique_response(example_text)
    assert critique.clarity_score >= 0
    assert critique.completeness_score >= 0
    assert critique.executability_score >= 0
