from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def load_summarizer() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "summarize_batch.py"
    spec = importlib.util.spec_from_file_location("batch15_summarize", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_severity_counts_reads_nested_cli_results() -> None:
    summarize = load_summarizer()
    report = {
        "results": [
            {
                "diagnostics": [
                    {"severity": "error", "rule": "semantic.contradiction.detected"},
                    {"severity": "warning", "rule": "graph.capability.orphaned"},
                    {"severity": "info", "rule": "description.quality-score"},
                ]
            }
        ]
    }

    assert summarize.severity_counts(report) == {"error": 1, "warning": 1, "info": 1}
    assert summarize.format_rule_counts(summarize.rule_counts(report, "error")) == (
        "semantic.contradiction.detected=1"
    )


def test_missing_json_report_is_not_counted_as_zero(tmp_path: Path) -> None:
    summarize = load_summarizer()

    report, status = summarize.load_json_report(tmp_path / "missing.json")

    assert report is None
    assert status == "missing"
    assert summarize.severity_counts(report) is None
    assert summarize.fmt_count_pair(None, None) == "n/a"


def test_collect_rows_marks_missing_phase_b_as_pending(tmp_path: Path) -> None:
    summarize = load_summarizer()
    repo_dir = tmp_path / "repo"
    skill_dir = repo_dir / "skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "STATUS").write_text("phase-a-ok\n")
    (skill_dir / "META.txt").write_text("sha: abc123\n")
    (skill_dir / "01-symbolic.txt").write_text("exit: 0\n")
    (skill_dir / "01-symbolic.json").write_text(json.dumps({"results": [{"diagnostics": []}]}))
    (skill_dir / "02-strict-vscode.txt").write_text("exit: 0\n")
    (skill_dir / "02-strict-vscode.json").write_text(json.dumps({"results": [{"diagnostics": []}]}))
    (skill_dir / "03-graph-analyze.txt").write_text("exit: 0\n")
    (skill_dir / "03-graph-analyze.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "diagnostics": [
                            {"severity": "warning", "rule": "graph.capability.orphaned"}
                        ]
                    }
                ]
            }
        )
    )
    (skill_dir / "04-graph-extracted.json").write_text(
        json.dumps({"capabilities": [{"id": "cap"}], "inputs": [], "outputs": [], "edges": []})
    )
    rows = summarize.collect_rows(tmp_path)

    assert len(rows) == 1
    row = rows[0]
    assert row["phase_b_done"] == 0
    assert row["graph_warn"] == 1
    assert row["crit_status"] == "missing"
    assert row["crit_err"] is None
    assert row["full_err"] is None
