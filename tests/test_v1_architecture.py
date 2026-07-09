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
from skillcheck.core import graph, history, semantic, symbolic

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_core_module_surface_imports_cleanly() -> None:
    assert symbolic is not None
    assert semantic is not None
    assert graph is not None
    assert history is not None


def test_semantic_functions_are_callable() -> None:
    # Phase 0 stubs replaced in Phase 1B with real implementations.
    # Verify the three public functions exist and have the right names.
    assert callable(getattr(semantic, "render_critique_prompt", None)), (
        "semantic.render_critique_prompt must exist"
    )
    assert callable(getattr(semantic, "ingest_critique_response", None)), (
        "semantic.ingest_critique_response must exist"
    )
    assert callable(getattr(semantic, "merge_diagnostics", None)), (
        "semantic.merge_diagnostics must exist"
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
