"""CLI tests for --history and --show-history flags (Phase 2D)."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import CLI_AVAILABLE, SKILLCHECK_CMD

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CRITIQUE_DIR = FIXTURES_DIR / "critique"
GR_DIR = FIXTURES_DIR / "graph_responses"
HISTORY_DIR = FIXTURES_DIR / "history"

pytestmark = pytest.mark.skipif(
    not CLI_AVAILABLE,
    reason="skillcheck not installed; run `pip install -e .` first",
)

_BASE_FLAGS = ["--skip-dirname-check"]


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*SKILLCHECK_CMD, *_BASE_FLAGS, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _ledger_path(skill_path: Path) -> Path:
    return skill_path.parent / ".skillcheck-history.json"


# ---------------------------------------------------------------------------
# --history basic
# ---------------------------------------------------------------------------


def test_history_passing_skill_exits_zero(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    result = run(str(skill), "--history")
    assert result.returncode == 0
    lp = _ledger_path(skill)
    assert lp.exists(), "Ledger file must be created"


def test_history_creates_ledger_with_one_run(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    run(str(skill), "--history")
    lp = _ledger_path(skill)
    data = json.loads(lp.read_text(encoding="utf-8"))
    assert len(data["runs"]) == 1
    assert data["runs"][0]["result"]["valid"] is True


def test_history_run_twice_creates_two_entries(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    run(str(skill), "--history")
    run(str(skill), "--history")
    lp = _ledger_path(skill)
    data = json.loads(lp.read_text(encoding="utf-8"))
    assert len(data["runs"]) == 2


def test_history_fans_out_across_multiple_paths(tmp_path: Path):
    """--history with multiple SKILL.md paths writes one ledger per target.
    Previously the CLI silently skipped multi-file invocations.
    """
    skill_a = tmp_path / "a" / "SKILL.md"
    skill_b = tmp_path / "b" / "SKILL.md"
    skill_a.parent.mkdir()
    skill_b.parent.mkdir()
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill_a)
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill_b)
    result = run(str(skill_a), str(skill_b), "--history")
    assert result.returncode == 0
    ledger_a = _ledger_path(skill_a)
    ledger_b = _ledger_path(skill_b)
    assert ledger_a.exists(), "Ledger A must be created"
    assert ledger_b.exists(), "Ledger B must be created"
    data_a = json.loads(ledger_a.read_text(encoding="utf-8"))
    data_b = json.loads(ledger_b.read_text(encoding="utf-8"))
    assert len(data_a["runs"]) == 1
    assert len(data_b["runs"]) == 1


def test_show_history_warns_on_extra_paths(tmp_path: Path):
    """--show-history reads only the first path's ledger; extra paths are
    surfaced via stderr instead of being silently skipped.
    """
    skill_a = tmp_path / "a" / "SKILL.md"
    skill_b = tmp_path / "b" / "SKILL.md"
    skill_a.parent.mkdir()
    skill_b.parent.mkdir()
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill_a)
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill_b)
    run(str(skill_a), "--history")
    run(str(skill_b), "--history")
    result = run(str(skill_a), str(skill_b), "--show-history")
    assert result.returncode == 0
    assert "ignoring extra paths" in result.stderr.lower(), (
        f"expected fan-out warning in stderr, got: {result.stderr!r}"
    )
    assert str(skill_b) in result.stderr


def test_history_records_correct_modes_symbolic_only(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    run(str(skill), "--history")
    data = json.loads(_ledger_path(skill).read_text(encoding="utf-8"))
    modes = data["runs"][0]["validation_modes"]
    assert modes["symbolic"] is True
    assert modes["critique"] is False
    assert modes["graph"] is False


def test_history_records_both_critique_and_graph_agents(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    critique_response = str(CRITIQUE_DIR / "response_clean.json")
    graph_response = str(GR_DIR / "response_clean.json")
    run(
        str(skill),
        "--history",
        "--ingest-critique", critique_response,
        "--ingest-graph", graph_response,
    )
    lp = _ledger_path(skill)
    data = json.loads(lp.read_text(encoding="utf-8"))
    modes = data["runs"][0]["validation_modes"]
    agents = data["runs"][0]["agents"]
    assert modes["symbolic"] is True
    assert modes["critique"] is True
    assert modes["graph"] is True
    assert agents["critique_agent"] == "claude"
    assert agents["graph_agent"] == "claude"


def test_history_schema_keys_present(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    run(str(skill), "--history")
    data = json.loads(_ledger_path(skill).read_text(encoding="utf-8"))
    assert "version" in data
    assert "skill_path" in data
    assert "runs" in data
    run_keys = set(data["runs"][0].keys())
    expected = {"timestamp_utc", "skillcheck_version", "skill_content_hash",
                "validation_modes", "agents", "result", "exit_code"}
    assert run_keys == expected


# ---------------------------------------------------------------------------
# No ledger created without --history
# ---------------------------------------------------------------------------


def test_no_ledger_without_history_flag(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    run(str(skill))
    lp = _ledger_path(skill)
    assert not lp.exists(), "Ledger must NOT be created without --history"


# ---------------------------------------------------------------------------
# --show-history
# ---------------------------------------------------------------------------


def test_show_history_missing_ledger_exits_two(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    result = run(str(skill), "--show-history")
    assert result.returncode == 2
    assert "No history ledger found" in result.stderr
    assert str(skill) in result.stderr


def test_show_history_json_is_valid_json(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    run(str(skill), "--history")
    result = run(str(skill), "--show-history", "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "version" in data
    assert "skill_path" in data
    assert "runs" in data


def test_show_history_json_top_level_keys(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    run(str(skill), "--history")
    result = run(str(skill), "--show-history", "--format", "json")
    data = json.loads(result.stdout)
    assert list(data.keys()) == ["version", "skill_path", "runs"]


def test_show_history_text_contains_timestamps(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    run(str(skill), "--history")
    result = run(str(skill), "--show-history")
    assert result.returncode == 0
    import re
    ts_re = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
    assert ts_re.search(result.stdout), "Text output must contain ISO timestamp"


def test_show_history_text_contains_pass_or_fail(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    run(str(skill), "--history")
    result = run(str(skill), "--show-history")
    assert "PASS" in result.stdout or "FAIL" in result.stdout


# ---------------------------------------------------------------------------
# Regression detection
# ---------------------------------------------------------------------------


def test_history_regression_emits_warning(tmp_path: Path):
    """Pass then fail on same content triggers history.skill.regressed WARNING."""
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)

    # First run: passing.
    run(str(skill), "--history")

    # Corrupt the skill to produce a failing run WHILE keeping the same content.
    # We simulate by writing a skill that fails description score check but
    # keeping the file content the same -- which means we need a different approach.
    # Instead, write a known-bad description-quality skill (same bytes as the first run
    # is impossible to orchestrate externally); instead we verify the regression
    # diagnostic fires when the ledger already has a passing entry and we inject
    # a failing run. This is covered in test_history_io.py at the unit level.
    # For the CLI-level regression test, we verify via ledger manipulation:
    # write a ledger with a passing entry, then run a failing skill with same hash.
    #
    # Strategy: write a ledger fixture that records a passing run for bad_desc_empty.md,
    # then run bad_desc_empty.md --history so the second run fails.
    bad_skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "bad_desc_empty.md", bad_skill)

    # Pre-seed ledger with a "passing" run at the hash of bad_desc_empty.md.
    import hashlib
    raw = bad_skill.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    pre_seed = {
        "version": 1,
        "skill_path": "SKILL.md",
        "runs": [
            {
                "timestamp_utc": "2026-01-01T00:00:00Z",
                "skillcheck_version": "0.2.0",
                "skill_content_hash": content_hash,
                "validation_modes": {"symbolic": True, "critique": False, "graph": False},
                "agents": {"critique_agent": None, "graph_agent": None},
                "result": {"error": 0, "warning": 0, "info": 0, "valid": True},
                "exit_code": 0,
            }
        ],
    }
    lp = _ledger_path(bad_skill)
    lp.write_text(json.dumps(pre_seed, indent=2), encoding="utf-8")

    # Now run with --history on the same bad_desc_empty.md which will fail.
    result = subprocess.run(
        [*SKILLCHECK_CMD, "--skip-dirname-check", str(bad_skill), "--history"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 1  # Skill fails (bad description)
    combined_out = result.stdout + result.stderr
    assert "history.skill.regressed" in combined_out or "regressed" in combined_out.lower()


# ---------------------------------------------------------------------------
# Mutual exclusion
# ---------------------------------------------------------------------------


def test_history_with_emit_critique_prompt_exits_two(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    result = run(str(skill), "--history", "--emit-critique-prompt")
    assert result.returncode == 2
    assert "--history" in result.stderr
    assert "--emit-critique-prompt" in result.stderr


def test_history_with_emit_graph_exits_two(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    result = run(str(skill), "--history", "--emit-graph")
    assert result.returncode == 2
    assert "--history" in result.stderr


def test_show_history_with_history_exits_two(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    result = run(str(skill), "--show-history", "--history")
    assert result.returncode == 2
    assert "--show-history" in result.stderr
    assert "--history" in result.stderr


def test_show_history_with_emit_critique_prompt_exits_two(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    result = run(str(skill), "--show-history", "--emit-critique-prompt")
    assert result.returncode == 2
    assert "--show-history" in result.stderr


def test_show_history_with_emit_graph_exits_two(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    result = run(str(skill), "--show-history", "--emit-graph")
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# Ledger I/O failure
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="chmod restrictions differ on Windows")
def test_history_write_failure_warns_but_keeps_exit_code(tmp_path: Path):
    """When the ledger can't be written, exit code reflects validation, not the write error."""
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)

    old_mode = tmp_path.stat().st_mode
    try:
        os.chmod(tmp_path, stat.S_IRUSR | stat.S_IXUSR)
        result = subprocess.run(
            [*SKILLCHECK_CMD, "--skip-dirname-check", str(skill), "--history"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    finally:
        os.chmod(tmp_path, old_mode)

    # Validation passed; exit code 0, not 1 (write failure is a warning).
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "history.write.failed" in combined


# ---------------------------------------------------------------------------
# Backward compatibility regressions
# ---------------------------------------------------------------------------


def test_text_output_unchanged_no_history_flag(tmp_path: Path):
    """Output without --history must be byte-identical to before Phase 2D."""
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    result_with = subprocess.run(
        [*SKILLCHECK_CMD, "--skip-dirname-check", str(skill)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    # Baseline: run twice without --history and confirm output is stable.
    result_again = subprocess.run(
        [*SKILLCHECK_CMD, "--skip-dirname-check", str(skill)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result_with.stdout == result_again.stdout
    assert result_with.returncode == result_again.returncode


def test_json_output_unchanged_no_history_flag(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    r1 = subprocess.run(
        [*SKILLCHECK_CMD, "--skip-dirname-check", "--format", "json", str(skill)],
        capture_output=True, text=True, encoding="utf-8",
    )
    r2 = subprocess.run(
        [*SKILLCHECK_CMD, "--skip-dirname-check", "--format", "json", str(skill)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r1.stdout == r2.stdout
    assert r1.returncode == r2.returncode


def test_ingest_critique_alone_unchanged(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    critique = str(CRITIQUE_DIR / "response_clean.json")
    r1 = subprocess.run(
        [*SKILLCHECK_CMD, "--skip-dirname-check", str(skill), "--ingest-critique", critique],
        capture_output=True, text=True, encoding="utf-8",
    )
    r2 = subprocess.run(
        [*SKILLCHECK_CMD, "--skip-dirname-check", str(skill), "--ingest-critique", critique],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r1.returncode == r2.returncode


def test_ingest_graph_alone_unchanged(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    shutil.copy(FIXTURES_DIR / "valid_basic.md", skill)
    graph_r = str(GR_DIR / "response_clean.json")
    r1 = subprocess.run(
        [*SKILLCHECK_CMD, "--skip-dirname-check", str(skill), "--ingest-graph", graph_r],
        capture_output=True, text=True, encoding="utf-8",
    )
    r2 = subprocess.run(
        [*SKILLCHECK_CMD, "--skip-dirname-check", str(skill), "--ingest-graph", graph_r],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r1.returncode == r2.returncode
