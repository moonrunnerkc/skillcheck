"""Tests for --format github (GitHub Actions workflow command output)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from skillcheck.cli import _format_github, _gha_escape
from skillcheck.result import Diagnostic, ValidationResult, Severity

from tests.conftest import FIXTURES_DIR


class TestGhaEscape:
    """Escape rules per the GHA workflow command spec."""

    def test_percent_escaped_first(self) -> None:
        assert _gha_escape("100%") == "100%25"

    def test_carriage_return_escaped(self) -> None:
        assert _gha_escape("line\rbreak") == "line%0Dbreak"

    def test_newline_escaped(self) -> None:
        assert _gha_escape("line\nbreak") == "line%0Abreak"

    def test_colon_escaped(self) -> None:
        assert _gha_escape("key:value") == "key%3Avalue"

    def test_comma_escaped(self) -> None:
        assert _gha_escape("a, b") == "a%2C b"

    def test_order_percent_before_others(self) -> None:
        assert _gha_escape("%\r\n:,") == "%25%0D%0A%3A%2C"

    def test_round_trip_all_five_chars(self) -> None:
        raw = "error: 50%\r\ncheck a, b"
        escaped = _gha_escape(raw)
        assert "%" not in escaped.replace("%25", "").replace("%0D", "").replace("%0A", "").replace("%3A", "").replace("%2C", "")
        assert "%25" in escaped
        assert "%0D" in escaped
        assert "%0A" in escaped
        assert "%3A" in escaped
        assert "%2C" in escaped


class TestFormatGithub:
    """Diagnostic-to-GHA workflow command mapping."""

    def _make_result(self, *diags: Diagnostic, path: str = "SKILL.md") -> list[ValidationResult]:
        return [ValidationResult(path=Path(path), diagnostics=list(diags))]

    def test_error_diagnostic_produces_error_command(self) -> None:
        d = Diagnostic(rule="frontmatter.name.required", severity=Severity.ERROR, message="name is required", line=1)
        output = _format_github(self._make_result(d))
        assert output.startswith("::error file=SKILL.md,line=1,title=skillcheck: frontmatter.name.required::name is required")

    def test_warning_diagnostic_produces_warning_command(self) -> None:
        d = Diagnostic(rule="frontmatter.name.reserved-word", severity=Severity.WARNING, message="reserved word", line=3)
        output = _format_github(self._make_result(d))
        assert output.startswith("::warning file=SKILL.md,line=3,title=skillcheck: frontmatter.name.reserved-word::reserved word")

    def test_info_diagnostic_produces_notice_command(self) -> None:
        d = Diagnostic(rule="frontmatter.field.ecosystem", severity=Severity.INFO, message="ecosystem field", line=5)
        output = _format_github(self._make_result(d))
        assert output.startswith("::notice file=SKILL.md,line=5,title=skillcheck: frontmatter.field.ecosystem::ecosystem field")

    def test_no_line_omits_line_property(self) -> None:
        d = Diagnostic(rule="some.rule", severity=Severity.WARNING, message="no line")
        output = _format_github(self._make_result(d))
        assert "line=" not in output
        assert output.startswith("::warning file=SKILL.md,title=skillcheck: some.rule::no line")

    def test_message_with_special_chars_escaped(self) -> None:
        d = Diagnostic(rule="test.escape", severity=Severity.ERROR, message="100%\r\n:,", line=2)
        output = _format_github(self._make_result(d, path="dir/SKILL.md"))
        assert "100%25%0D%0A%3A%2C" in output
        assert "::error file=dir/SKILL.md" in output

    def test_multiple_diagnostics_across_files(self) -> None:
        d1 = Diagnostic(rule="r1", severity=Severity.ERROR, message="e1", line=1)
        d2 = Diagnostic(rule="r2", severity=Severity.WARNING, message="w2", line=2)
        results = [
            ValidationResult(path=Path("a/SKILL.md"), diagnostics=[d1]),
            ValidationResult(path=Path("b/SKILL.md"), diagnostics=[d2]),
        ]
        output = _format_github(results)
        lines = output.strip().split("\n")
        assert len(lines) == 2
        assert lines[0].startswith("::error file=a/SKILL.md")
        assert lines[1].startswith("::warning file=b/SKILL.md")


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["skillcheck", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_format_github_cli_produces_gha_commands() -> None:
    result = _run(str(FIXTURES_DIR / "bad_name_caps.md"), "--format", "github", "--skip-dirname-check")
    assert result.returncode == 1
    assert "::error " in result.stdout
    assert "title=skillcheck:" in result.stdout


def test_format_github_cli_with_warning() -> None:
    result = _run(str(FIXTURES_DIR / "bad_name_reserved.md"), "--format", "github", "--skip-dirname-check")
    assert "::warning " in result.stdout


def test_format_github_cli_with_info() -> None:
    result = _run(str(FIXTURES_DIR / "license_field.md"), "--format", "github", "--skip-dirname-check")
    assert "::notice " in result.stdout