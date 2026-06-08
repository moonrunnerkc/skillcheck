from __future__ import annotations

import inspect
from pathlib import Path

from skillcheck import (
    Diagnostic,
    ParsedSkill,
    ParseError,
    Severity,
    ValidationResult,
    validate,
)
from skillcheck.agents.base import SelfCritiquePrompt
from skillcheck.core import graph, history, reporter, semantic, symbolic

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_core_module_surface_imports_cleanly() -> None:
    assert symbolic is not None
    assert semantic is not None
    assert graph is not None
    assert history is not None
    assert reporter is not None


def test_semantic_functions_are_callable() -> None:
    # Phase 0 stubs replaced in Phase 1B with real implementations.
    # Verify the three public functions exist and have the right names.
    assert callable(getattr(semantic, "render_critique_prompt", None)), (
        "semantic.render_critique_prompt must exist"
    )
    assert callable(getattr(semantic, "ingest_critique_response", None)), (
        "semantic.ingest_critique_response must exist"
    )
    assert callable(getattr(semantic, "merge_critique_diagnostics", None)), (
        "semantic.merge_critique_diagnostics must exist"
    )


def test_graph_extract_heuristic_is_callable() -> None:
    # Phase 0 stub replaced in Phase 2A; verify the real extractor is present.
    assert callable(getattr(graph, "extract_graph_heuristic", None)), (
        "graph.extract_graph_heuristic must exist"
    )


def test_history_module_is_implemented() -> None:
    # Phase 2D replaced the Phase 0 stub with a real implementation.
    # Verify the key callables exist and are not stubs.
    assert callable(getattr(history, "append_run", None)), (
        "history.append_run must exist (Phase 2D implementation)"
    )
    assert callable(getattr(history, "load_ledger", None)), (
        "history.load_ledger must exist"
    )
    assert callable(getattr(history, "save_ledger", None)), (
        "history.save_ledger must exist"
    )
    assert callable(getattr(history, "check_regression", None)), (
        "history.check_regression must exist"
    )


def test_reporter_functions_return_correct_types() -> None:
    result = ValidationResult(path=FIXTURES_DIR / "valid_basic.md", diagnostics=[])

    md = reporter.render_markdown_report(result)
    assert isinstance(md, str)
    assert "PASS" in md
    assert "valid_basic.md" in md

    payload = reporter.render_json_report(result)
    assert isinstance(payload, dict)
    assert payload["valid"] is True
    assert payload["error_count"] == 0
    assert payload["diagnostics"] == []


def test_reporter_markdown_fail_path_contains_table_header() -> None:
    result = ValidationResult(
        path=FIXTURES_DIR / "bad_name_caps.md",
        diagnostics=[
            Diagnostic(
                rule="frontmatter.name.invalid-chars",
                severity=Severity.ERROR,
                message="name contains uppercase characters",
                line=2,
            ),
        ],
    )

    md = reporter.render_markdown_report(result)
    assert "FAIL" in md
    for header in ("Line", "Severity", "Rule", "Message"):
        assert header in md
    assert "frontmatter.name.invalid-chars" in md


def test_reporter_json_counts_mixed_severities() -> None:
    result = ValidationResult(
        path=FIXTURES_DIR / "valid_basic.md",
        diagnostics=[
            Diagnostic(rule="r.error", severity=Severity.ERROR, message="boom"),
            Diagnostic(rule="r.warn1", severity=Severity.WARNING, message="meh"),
            Diagnostic(rule="r.warn2", severity=Severity.WARNING, message="also meh"),
            Diagnostic(rule="r.info", severity=Severity.INFO, message="fyi"),
        ],
    )

    payload = reporter.render_json_report(result)
    assert payload["error_count"] == 1
    assert payload["warning_count"] == 2
    assert payload["info_count"] == 1
    assert len(payload["diagnostics"]) == 4
    assert payload["valid"] is False


def test_reporter_json_path_is_string() -> None:
    result = ValidationResult(path=FIXTURES_DIR / "valid_basic.md", diagnostics=[])

    payload = reporter.render_json_report(result)
    assert isinstance(payload["path"], str)
    assert payload["path"] == str(result.path)


def test_agent_base_interface_shape() -> None:
    # SelfCritiquePrompt is now a concrete class with a render() method.
    render_sig = inspect.signature(SelfCritiquePrompt.render)
    assert list(render_sig.parameters.keys()) == ["self", "skill"]
    assert render_sig.return_annotation in {str, "str"}


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
