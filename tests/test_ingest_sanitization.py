"""Terminal-escape sanitization for untrusted ingested agent responses.

A critique or graph response can carry raw ANSI escape sequences that, printed
straight to a terminal, forge output (a fake PASS line, a cleared screen). The
sanitizer escapes control characters to a visible, inert form before they reach
the report. The JSON output path is unaffected: json.dumps already escapes
control characters.
"""

from __future__ import annotations

from skillcheck.agents._ingest import sanitize_ingested_text
from skillcheck.core.graph import Capability, CapabilityGraph
from skillcheck.core.graph_render import render_graph_json, render_graph_text
from skillcheck.core.semantic import ingest_critique_response
from skillcheck.parser import parse
from tests.conftest import FIXTURES_DIR

_ESC = chr(27)
_ANSI_RESPONSE = FIXTURES_DIR / "critique" / "response_ansi_injection.json"


def test_sanitize_escapes_ansi_escape_char() -> None:
    out = sanitize_ingested_text(f"{_ESC}[32mgreen{_ESC}[0m")
    assert _ESC not in out
    assert out == r"\x1b[32mgreen\x1b[0m"


def test_sanitize_escapes_newlines_and_tabs() -> None:
    out = sanitize_ingested_text("line1\nline2\tend")
    assert "\n" not in out
    assert "\t" not in out
    assert out == r"line1\nline2\tend"


def test_sanitize_leaves_normal_text_unchanged() -> None:
    text = "Validates SKILL.md files against the spec (v1.4)."
    assert sanitize_ingested_text(text) == text


def test_ingested_critique_message_has_no_control_chars() -> None:
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    diagnostics = ingest_critique_response(skill, _ANSI_RESPONSE.read_text(encoding="utf-8"))
    context_diags = [d for d in diagnostics if d.rule == "semantic.context.missing"]
    assert context_diags, "expected a semantic.context.missing diagnostic"
    message = context_diags[0].message
    assert _ESC not in message
    assert not any(ord(ch) < 0x20 for ch in message)
    assert "fake PASS" in message  # content preserved, just inert


def _graph_with_hostile_name() -> CapabilityGraph:
    cap = Capability(id="a1", name=f"{_ESC}[2Kfake PASS", description="", line=1)
    return CapabilityGraph(
        capabilities=(cap,), inputs=(), outputs=(), edges=(), source="agent"
    )


def test_graph_text_render_escapes_node_names() -> None:
    rendered = render_graph_text(_graph_with_hostile_name())
    assert _ESC not in rendered
    assert r"\x1b[2Kfake PASS" in rendered


def test_graph_json_render_stays_safe_and_raw() -> None:
    # json.dumps escapes the control char to ; no raw ESC leaks, and the
    # sanitizer is not applied a second time on the JSON path.
    rendered = render_graph_json(_graph_with_hostile_name())
    assert _ESC not in rendered
    assert "\\u001b" in rendered
