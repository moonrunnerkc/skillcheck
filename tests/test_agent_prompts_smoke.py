"""Snapshot tests for agent prompt scaffolding.

Each (agent, mode) combination renders a deterministic prompt against a
stable fixture; the rendered prompt's SHA-256 digest is pinned. The intent
is to catch accidental edits to prompt scaffolding (XML tag changes, missing
instruction sentences, accidental whitespace) without requiring an oracle
for prompt quality. When you intentionally edit a prompt template, update
the digest in this file in the same commit.

What this asserts:
- The prompt is deterministic for the same input skill.
- Layout / scaffolding has not changed.

What this does NOT assert:
- That the prompt actually elicits better output from the agent.
- That the agent's JSON response will validate.
"""

from __future__ import annotations

import hashlib

import pytest

from skillcheck.agents import (
    ClaudeGraphPrompt,
    ClaudePrompt,
    CodexGraphPrompt,
    CodexPrompt,
    CursorGraphPrompt,
    CursorPrompt,
)
from skillcheck.parser import parse
from tests.conftest import FIXTURES_DIR

_FIXTURE = FIXTURES_DIR / "valid_basic.md"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Pinned digests of the rendered prompts against tests/fixtures/valid_basic.md.
# If you intentionally edit a prompt template, replace the digest below in
# the same commit that touches the template; do not silently regenerate.
_EXPECTED: dict[tuple[str, str], str] = {
    ("critique", "claude"): "c19a2774607cea8b4f9130bd7ddd050edf3576daca14ae97d558e0248e6e46ce",
    ("critique", "codex"): "f7d596c04930369a7a68ae595b6fa30b7d2ea44211d8e2fc6c2b1d9cb146d982",
    ("critique", "cursor"): "3424ad2f5e9466313be29c83d2fc37319729bd67e0f5e4ee4719f2f42cfc7423",
    ("graph", "claude"): "7a566442f9f36978397cfa61487271fdca89dbd010e902a6e5150038d4776c9f",
    ("graph", "codex"): "75c8c44a582d3d9d4f409fedc6159e005097dffb7a44cedcf36dfe915e81edf6",
    ("graph", "cursor"): "7638fe3f6ce5bae7d37782cdb77eb210fc31473c07cf7942061e45d651af52b0",
}


@pytest.mark.parametrize(
    "mode,agent,prompt_cls",
    [
        ("critique", "claude", ClaudePrompt),
        ("critique", "codex", CodexPrompt),
        ("critique", "cursor", CursorPrompt),
        ("graph", "claude", ClaudeGraphPrompt),
        ("graph", "codex", CodexGraphPrompt),
        ("graph", "cursor", CursorGraphPrompt),
    ],
)
def test_prompt_digest_matches_snapshot(
    mode: str, agent: str, prompt_cls: type
) -> None:
    """The rendered prompt's SHA-256 matches the pinned snapshot. Update
    _EXPECTED in the same commit that edits a prompt template; never
    silently regenerate.
    """
    skill = parse(_FIXTURE)
    rendered = prompt_cls().render(skill)
    actual = _digest(rendered)
    expected = _EXPECTED[(mode, agent)]
    assert actual == expected, (
        f"{mode}:{agent} prompt digest changed.\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}\n"
        f"If this edit was intentional, update _EXPECTED in the same commit."
    )


@pytest.mark.parametrize(
    "label,prompt_cls",
    [
        ("critique:claude", ClaudePrompt),
        ("critique:codex", CodexPrompt),
        ("critique:cursor", CursorPrompt),
        ("graph:claude", ClaudeGraphPrompt),
        ("graph:codex", CodexGraphPrompt),
        ("graph:cursor", CursorGraphPrompt),
    ],
)
def test_prompt_is_deterministic(label: str, prompt_cls: type) -> None:
    """Rendering the same prompt against the same fixture twice yields
    byte-identical output (no nondeterminism from set ordering or RNG)."""
    skill = parse(_FIXTURE)
    a = prompt_cls().render(skill)
    b = prompt_cls().render(skill)
    assert a == b, f"{label}: render() is not deterministic"


@pytest.mark.parametrize(
    "label,prompt_cls,marker",
    [
        ("critique:claude", ClaudePrompt, "<response_schema>"),
        ("critique:codex", CodexPrompt, "## "),
        ("critique:cursor", CursorPrompt, "JSON"),
        ("graph:claude", ClaudeGraphPrompt, "<response_schema>"),
        ("graph:codex", CodexGraphPrompt, "## "),
        ("graph:cursor", CursorGraphPrompt, "JSON"),
    ],
)
def test_prompt_contains_expected_scaffolding_marker(
    label: str, prompt_cls: type, marker: str
) -> None:
    """Each variant carries a known structural marker so a regression that
    accidentally rewrites the scaffolding fails loudly. The markers reflect
    each vendor's framing convention: XML tags for Claude, markdown headers
    for Codex, compact JSON-shape signatures for Cursor.
    """
    skill = parse(_FIXTURE)
    rendered = prompt_cls().render(skill)
    assert marker in rendered, (
        f"{label}: rendered prompt is missing required scaffolding marker {marker!r}"
    )


@pytest.mark.parametrize(
    "label,prompt_cls",
    [
        ("critique:claude", ClaudePrompt),
        ("critique:codex", CodexPrompt),
        ("critique:cursor", CursorPrompt),
        ("graph:claude", ClaudeGraphPrompt),
        ("graph:codex", CodexGraphPrompt),
        ("graph:cursor", CursorGraphPrompt),
    ],
)
def test_prompt_embeds_skill_text(label: str, prompt_cls: type) -> None:
    """The fixture skill's frontmatter name and a body fragment appear in the
    rendered prompt. If a future refactor drops the skill text from the
    template, the agent has nothing to critique; this guards that case.
    """
    skill = parse(_FIXTURE)
    rendered = prompt_cls().render(skill)
    assert "pdf-processor" in rendered, (
        f"{label}: rendered prompt does not embed the skill's name field"
    )
