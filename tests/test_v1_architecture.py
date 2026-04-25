from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from skillcheck import (
    Diagnostic,
    ParseError,
    ParsedSkill,
    Severity,
    ValidationResult,
    validate,
)
from skillcheck.agents.base import SelfCritiqueTemplate
from skillcheck.core import graph, history, reporter, semantic, symbolic


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_core_module_surface_imports_cleanly() -> None:
    assert symbolic is not None
    assert semantic is not None
    assert graph is not None
    assert history is not None
    assert reporter is not None


def test_semantic_stub_functions_raise_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Semantic engine requires --agent-reason and lands in v1.0."):
        semantic.build_self_critique_prompt(FIXTURES_DIR / "valid_basic.md", "claude")

    with pytest.raises(NotImplementedError, match="Semantic engine requires --agent-reason and lands in v1.0."):
        semantic.validate_agent_report({}, "claude")


def test_graph_stub_function_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Capability graph extraction lands in v1.0."):
        graph.extract_capability_graph(FIXTURES_DIR / "valid_basic.md")


def test_history_stub_function_raises_not_implemented() -> None:
    snapshot = history.ValidationSnapshot(
        timestamp="2026-04-24T00:00:00Z",
        path="tests/fixtures/valid_basic.md",
        valid=True,
        metadata={},
    )
    with pytest.raises(NotImplementedError, match="Validation history ledger lands in v1.0."):
        history.append_validation_snapshot(FIXTURES_DIR / ".skillcheck-history.json", snapshot)


def test_reporter_stub_functions_raise_not_implemented() -> None:
    result = ValidationResult(path=FIXTURES_DIR / "valid_basic.md", diagnostics=[])

    with pytest.raises(NotImplementedError, match="Reasoning-trace reporting lands in v1.0."):
        reporter.render_markdown_report(result)

    with pytest.raises(NotImplementedError, match="Reasoning-trace reporting lands in v1.0."):
        reporter.render_json_report(result)


def test_agent_base_interface_shape() -> None:
    members = inspect.getmembers(SelfCritiqueTemplate, predicate=inspect.isfunction)
    member_names = {name for name, _ in members if not name.startswith("__")}
    assert member_names == {"build_prompt", "validate_response"}

    agent_name_attr = inspect.getattr_static(SelfCritiqueTemplate, "agent_name")
    assert isinstance(agent_name_attr, property)

    build_prompt_signature = inspect.signature(SelfCritiqueTemplate.build_prompt)
    assert list(build_prompt_signature.parameters.keys()) == [
        "self",
        "skill_path",
        "skill_text",
    ]
    assert build_prompt_signature.return_annotation in {str, "str"}

    validate_response_signature = inspect.signature(SelfCritiqueTemplate.validate_response)
    assert list(validate_response_signature.parameters.keys()) == ["self", "payload"]
    assert validate_response_signature.return_annotation in {
        dict[str, Any],
        "dict[str, Any]",
    }


def test_public_api_exports_unchanged() -> None:
    assert validate is symbolic.validate
    assert ValidationResult.__name__ == "ValidationResult"
    assert Diagnostic.__name__ == "Diagnostic"
    assert Severity.__name__ == "Severity"
    assert ParsedSkill.__name__ == "ParsedSkill"
    assert ParseError.__name__ == "ParseError"


def test_validate_smoke_for_known_good_and_bad_fixtures() -> None:
    good_result = validate(FIXTURES_DIR / "valid_basic.md", skip_dirname_check=True)
    assert good_result.valid is True

    bad_result = validate(FIXTURES_DIR / "bad_name_caps.md")
    assert bad_result.valid is False
    assert any(d.rule == "frontmatter.name.invalid-chars" for d in bad_result.diagnostics)
