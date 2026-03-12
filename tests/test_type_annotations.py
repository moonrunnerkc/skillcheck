"""Tests for Fix 5: Callable return type annotations."""

from collections.abc import Callable

from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic
from skillcheck.rules.compat import make_strict_vscode_rule
from skillcheck.rules.description import make_min_score_rule


def test_make_min_score_rule_returns_callable():
    """make_min_score_rule returns a proper Callable, not a bare function."""
    rule = make_min_score_rule(50)
    assert callable(rule)
    assert isinstance(rule, Callable)


def test_make_strict_vscode_rule_returns_callable():
    """make_strict_vscode_rule returns a proper Callable, not a bare function."""
    rule = make_strict_vscode_rule()
    assert callable(rule)
    assert isinstance(rule, Callable)
