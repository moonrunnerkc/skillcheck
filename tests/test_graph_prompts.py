"""Tests for agent-specific graph-extraction prompt variants."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillcheck.agents import GRAPH_AGENTS, get_graph_prompt
from skillcheck.agents.graph_base import GraphExtractionPrompt
from skillcheck.agents.graph_claude import ClaudeGraphPrompt
from skillcheck.agents.graph_codex import CodexGraphPrompt
from skillcheck.agents.graph_cursor import CursorGraphPrompt
from skillcheck.parser import parse

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GRAPH_DIR = FIXTURES_DIR / "graph"


def _skill():
    return parse(GRAPH_DIR / "skill_basic_io.md")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_graph_agents_registry_contains_all_variants() -> None:
    assert set(GRAPH_AGENTS.keys()) == {"claude", "codex", "cursor"}


def test_get_graph_prompt_returns_claude() -> None:
    prompt = get_graph_prompt("claude")
    assert isinstance(prompt, ClaudeGraphPrompt)


def test_get_graph_prompt_returns_codex() -> None:
    assert isinstance(get_graph_prompt("codex"), CodexGraphPrompt)


def test_get_graph_prompt_returns_cursor() -> None:
    assert isinstance(get_graph_prompt("cursor"), CursorGraphPrompt)


def test_get_graph_prompt_unknown_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown graph agent") as exc_info:
        get_graph_prompt("gpt-4o")
    msg = str(exc_info.value)
    assert "gpt-4o" in msg
    assert "claude" in msg
    assert "codex" in msg
    assert "cursor" in msg


def test_all_graph_agent_ids_match_registry_keys() -> None:
    for key, cls in GRAPH_AGENTS.items():
        assert cls.AGENT_ID == key


# ---------------------------------------------------------------------------
# Claude prompt structure
# ---------------------------------------------------------------------------


def test_claude_graph_render_contains_xml_skill_tag() -> None:
    rendered = ClaudeGraphPrompt().render(_skill())
    assert "<skill_to_analyze>" in rendered
    assert "</skill_to_analyze>" in rendered


def test_claude_graph_render_contains_xml_schema_tag() -> None:
    rendered = ClaudeGraphPrompt().render(_skill())
    assert "<response_schema>" in rendered
    assert "</response_schema>" in rendered


def test_claude_graph_render_contains_worked_example_tag() -> None:
    rendered = ClaudeGraphPrompt().render(_skill())
    assert "<worked_example>" in rendered


def test_claude_graph_render_contains_skill_body() -> None:
    skill = _skill()
    rendered = ClaudeGraphPrompt().render(skill)
    assert "Generate report" in rendered


def test_claude_graph_render_no_markdown_headers() -> None:
    rendered = ClaudeGraphPrompt().render(_skill())
    assert "### " not in rendered


def test_claude_graph_render_is_deterministic() -> None:
    skill = _skill()
    assert ClaudeGraphPrompt().render(skill) == ClaudeGraphPrompt().render(skill)


# ---------------------------------------------------------------------------
# Codex prompt structure
# ---------------------------------------------------------------------------


def test_codex_graph_render_contains_markdown_schema_header() -> None:
    rendered = CodexGraphPrompt().render(_skill())
    assert "### Schema" in rendered


def test_codex_graph_render_contains_markdown_skill_header() -> None:
    rendered = CodexGraphPrompt().render(_skill())
    assert "### Skill" in rendered


def test_codex_graph_render_no_xml_tags() -> None:
    rendered = CodexGraphPrompt().render(_skill())
    assert "<skill_to_analyze>" not in rendered
    assert "<response_schema>" not in rendered


def test_codex_graph_render_contains_skill_body() -> None:
    rendered = CodexGraphPrompt().render(_skill())
    assert "Generate report" in rendered


def test_codex_graph_render_is_deterministic() -> None:
    skill = _skill()
    assert CodexGraphPrompt().render(skill) == CodexGraphPrompt().render(skill)


# ---------------------------------------------------------------------------
# Cursor prompt structure
# ---------------------------------------------------------------------------


def test_cursor_graph_render_no_xml_tags() -> None:
    rendered = CursorGraphPrompt().render(_skill())
    assert "<skill_to_analyze>" not in rendered


def test_cursor_graph_render_no_markdown_headers() -> None:
    rendered = CursorGraphPrompt().render(_skill())
    assert "### " not in rendered


def test_cursor_graph_render_shorter_than_claude() -> None:
    skill = _skill()
    claude_len = len(ClaudeGraphPrompt().render(skill))
    cursor_len = len(CursorGraphPrompt().render(skill))
    assert cursor_len < claude_len


def test_cursor_graph_render_is_deterministic() -> None:
    skill = _skill()
    assert CursorGraphPrompt().render(skill) == CursorGraphPrompt().render(skill)


def test_cursor_graph_render_contains_skill_body() -> None:
    rendered = CursorGraphPrompt().render(_skill())
    assert "Generate report" in rendered


# ---------------------------------------------------------------------------
# Cross-variant invariants
# ---------------------------------------------------------------------------


def test_all_variants_render_different_prompts() -> None:
    skill = _skill()
    renders = {key: cls().render(skill) for key, cls in GRAPH_AGENTS.items()}
    # All three must be distinct.
    assert len(set(renders.values())) == 3


def test_all_variants_include_body_relative_line_hint() -> None:
    skill = _skill()
    for key, cls in GRAPH_AGENTS.items():
        rendered = cls().render(skill)
        assert "body" in rendered.lower() or "---" in rendered, (
            f"{key} prompt should hint at body-relative line numbering"
        )
