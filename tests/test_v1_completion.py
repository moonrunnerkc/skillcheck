"""Completion tests for v1 upgrade-guide compatibility flags."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import CLI_AVAILABLE, FIXTURES_DIR, SKILLCHECK_CMD

pytestmark = pytest.mark.skipif(
    not CLI_AVAILABLE,
    reason="skillcheck not installed; run `pip install -e .` first",
)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*SKILLCHECK_CMD, "--skip-dirname-check", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_format_md_outputs_markdown_report() -> None:
    result = run(str(FIXTURES_DIR / "valid_basic.md"), "--format", "md")
    assert result.returncode == 0
    assert result.stdout.startswith("# skillcheck report")


def test_format_agent_outputs_agent_report() -> None:
    result = run(str(FIXTURES_DIR / "valid_basic.md"), "--format", "agent")
    assert result.returncode == 0
    assert "skillcheck agent report" in result.stdout
    assert "next_actions:" in result.stdout


def test_agent_reason_emits_combined_packet() -> None:
    result = run(str(FIXTURES_DIR / "valid_basic.md"), "--agent-reason", "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    packet = payload["agent_reason"][0]
    assert "critique_prompt" in packet
    assert "graph_prompt" in packet


def test_semantic_enables_graph_analysis() -> None:
    graph_fixture = FIXTURES_DIR / "graph" / "skill_orphan_capability.md"
    result = run(str(graph_fixture), "--semantic")
    assert result.returncode == 0
    assert "graph.capability.orphaned" in result.stdout


def test_activation_hypotheses_json() -> None:
    result = run(str(FIXTURES_DIR / "valid_basic.md"), "--activation-hypotheses", "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["hypotheses"]
    assert "entropy" in payload


def test_skillcheck_toml_applies_defaults(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    (tmp_path / "skillcheck.toml").write_text(
        'format = "json"\nmax-lines = 1\nskip-dirname-check = true\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [*SKILLCHECK_CMD, str(skill)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    rules = [d["rule"] for r in payload["results"] for d in r["diagnostics"]]
    assert "sizing.body.line-count" in rules


def test_json_diagnostics_include_source_and_confidence() -> None:
    result = run(str(FIXTURES_DIR / "valid_basic.md"), "--max-lines", "1", "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    diagnostic = payload["results"][0]["diagnostics"][0]
    assert "source" in diagnostic
    assert "confidence" in diagnostic
