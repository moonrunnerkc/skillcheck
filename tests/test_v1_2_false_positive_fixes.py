from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from skillcheck import config as runtime_config
from skillcheck.config_loader import load_config
from skillcheck.core import validate
from skillcheck.parser import parse
from skillcheck.result import Severity
from skillcheck.rules.frontmatter import (
    check_description_person_voice,
    check_name_reserved_words,
    check_unknown_fields,
)
from tests.conftest import FIXTURES_DIR


@pytest.fixture(autouse=True)
def reset_extension_fields():
    runtime_config.set_extension_fields(())
    yield
    runtime_config.set_extension_fields(())


def _rules(path: Path, **kwargs) -> list[str]:
    result = validate(path, **kwargs)
    return [diagnostic.rule for diagnostic in result.diagnostics]


def _assert_ecosystem_field(path: Path, field: str) -> None:
    skill = parse(path)
    diagnostics = check_unknown_fields(skill)
    assert not any(
        d.rule == "frontmatter.field.unknown" and d.severity == Severity.WARNING
        for d in diagnostics
    )
    ecosystem = [d for d in diagnostics if d.rule == "frontmatter.field.ecosystem"]
    assert len(ecosystem) == 1
    assert ecosystem[0].severity == Severity.INFO
    assert field in ecosystem[0].message


def test_license_field_is_ecosystem_info() -> None:
    _assert_ecosystem_field(FIXTURES_DIR / "license_field.md", "license")


def test_homepage_field_is_ecosystem_info() -> None:
    _assert_ecosystem_field(FIXTURES_DIR / "homepage_field.md", "homepage")


def test_repository_field_is_ecosystem_info() -> None:
    _assert_ecosystem_field(FIXTURES_DIR / "repository_field.md", "repository")


def test_unknown_field_still_warns() -> None:
    skill = parse(FIXTURES_DIR / "unknown_field.md")
    diagnostics = check_unknown_fields(skill)
    unknown = [d for d in diagnostics if d.rule == "frontmatter.field.unknown"]
    assert len(unknown) == 1
    assert unknown[0].severity == Severity.WARNING
    assert "xyzzy" in unknown[0].message


def test_user_extension_field_is_silent() -> None:
    fixture_dir = FIXTURES_DIR / "user_extension"
    loaded_config = load_config(fixture_dir / "skillcheck.toml")
    runtime_config.set_extension_fields(loaded_config.extension_fields)
    skill = parse(fixture_dir / "user_extension_field.md")
    assert check_unknown_fields(skill) == []


def test_claude_api_name_warns_without_error() -> None:
    skill = parse(FIXTURES_DIR / "claude_api_name.md")
    diagnostics = check_name_reserved_words(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.name.reserved-word"
    assert diagnostics[0].severity == Severity.WARNING
    assert diagnostics[0].source == "advisory"
    assert diagnostics[0].confidence == "low"


def test_claude_api_name_validation_passes() -> None:
    result = validate(FIXTURES_DIR / "claude_api_name.md", skip_dirname_check=True)
    assert result.valid is True
    warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
    assert [d.rule for d in warnings] == ["frontmatter.name.reserved-word"]


def test_canvas_design_pattern_warns_without_error() -> None:
    skill = parse(FIXTURES_DIR / "canvas_design_pattern.md")
    diagnostics = check_description_person_voice(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.description.person-voice"
    assert diagnostics[0].severity == Severity.WARNING
    assert "You should" in diagnostics[0].message


def test_canvas_design_pattern_validation_passes() -> None:
    result = validate(FIXTURES_DIR / "canvas_design_pattern.md", skip_dirname_check=True)
    assert result.valid is True
    warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
    assert [d.rule for d in warnings] == ["frontmatter.description.person-voice"]


def _assert_template_skips_deployment_checks(path: Path) -> None:
    rules = _rules(path, strict_vscode=True)
    assert "template.detected" in rules
    assert "frontmatter.name.directory-mismatch" not in rules
    assert "compat.vscode-dirname" not in rules
    assert "description.quality-score" not in rules


def test_template_explicit_flag_skips_deployment_checks() -> None:
    _assert_template_skips_deployment_checks(FIXTURES_DIR / "template_explicit_flag.md")


def test_template_placeholder_description_skips_deployment_checks() -> None:
    _assert_template_skips_deployment_checks(
        FIXTURES_DIR / "template_placeholder_description.md"
    )


def test_template_directory_skips_deployment_checks() -> None:
    _assert_template_skips_deployment_checks(FIXTURES_DIR / "templates" / "SKILL.md")


def test_template_detection_keeps_body_budget_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime_config, "BODY_TOKEN_BUDGET", 1)
    rules = _rules(FIXTURES_DIR / "template_with_real_violations.md", strict_vscode=True)
    assert "template.detected" in rules
    assert "disclosure.body-budget" in rules


def test_non_template_placeholder_word_documents_false_positive() -> None:
    # The detector favors recall, so this real skill is intentionally flagged.
    _assert_template_skips_deployment_checks(
        FIXTURES_DIR / "non_template_with_placeholder_word.md"
    )


CLI_AVAILABLE = shutil.which("skillcheck") is not None


@pytest.mark.skipif(not CLI_AVAILABLE, reason="skillcheck command is not installed")
def test_claude_api_name_cli_exit_code_zero() -> None:
    result = subprocess.run(
        [
            "skillcheck",
            "--skip-dirname-check",
            str(FIXTURES_DIR / "claude_api_name.md"),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    diagnostics = payload["results"][0]["diagnostics"]
    reserved = [d for d in diagnostics if d["rule"] == "frontmatter.name.reserved-word"]
    assert reserved[0]["severity"] == "warning"


@pytest.mark.skipif(not CLI_AVAILABLE, reason="skillcheck command is not installed")
def test_canvas_design_pattern_cli_exit_code_zero() -> None:
    result = subprocess.run(
        [
            "skillcheck",
            "--skip-dirname-check",
            str(FIXTURES_DIR / "canvas_design_pattern.md"),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    diagnostics = payload["results"][0]["diagnostics"]
    voice = [
        d
        for d in diagnostics
        if d["rule"] == "frontmatter.description.person-voice"
    ]
    assert voice[0]["severity"] == "warning"
