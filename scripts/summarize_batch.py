#!/usr/bin/env python3
"""Summarize skillcheck batch-run artifacts."""
from __future__ import annotations

from collections import Counter
import argparse
import csv
import json
from pathlib import Path

SEVERITIES = ("error", "warning", "info")


def load_json_report(path: Path) -> tuple[dict | None, str]:
    if not path.is_file():
        return None, "missing"
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None, "invalid"
    if not isinstance(data, dict):
        return None, "invalid"
    return data, "ok"


def iter_diagnostics(report: dict) -> list[dict]:
    """Return diagnostics from both legacy and CLI report JSON shapes."""
    diagnostics: list[dict] = []
    top_level = report.get("diagnostics")
    if isinstance(top_level, list):
        diagnostics.extend(d for d in top_level if isinstance(d, dict))

    results = report.get("results")
    if isinstance(results, list):
        for result in results:
            if not isinstance(result, dict):
                continue
            result_diags = result.get("diagnostics")
            if isinstance(result_diags, list):
                diagnostics.extend(d for d in result_diags if isinstance(d, dict))

    return diagnostics


def severity_counts(report: dict | None) -> dict[str, int] | None:
    if report is None:
        return None
    counts = dict.fromkeys(SEVERITIES, 0)
    for diag in iter_diagnostics(report):
        sev = (diag.get("severity") or "").lower()
        if sev in counts:
            counts[sev] += 1
    return counts


def rule_counts(report: dict | None, severity: str | None = None) -> Counter[str]:
    counts: Counter[str] = Counter()
    if report is None:
        return counts
    for diag in iter_diagnostics(report):
        if severity is not None and (diag.get("severity") or "").lower() != severity:
            continue
        rule = diag.get("rule")
        if isinstance(rule, str) and rule:
            counts[rule] += 1
    return counts


def format_rule_counts(counts: Counter[str]) -> str:
    return "; ".join(f"{rule}={count}" for rule, count in counts.most_common())


def collection_len(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def graph_shape(graph: dict | None) -> tuple[int | None, int | None, int | None, int | None]:
    if graph is None:
        return None, None, None, None
    return (
        collection_len(graph.get("capabilities")),
        collection_len(graph.get("inputs")),
        collection_len(graph.get("outputs")),
        collection_len(graph.get("edges")),
    )


def read_meta(skill_dir: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    meta_file = skill_dir / "META.txt"
    if meta_file.is_file():
        for line in meta_file.read_text().splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
    return meta


def read_exit_code(path: Path) -> int | None:
    if not path.is_file():
        return None
    for line in reversed(path.read_text(errors="replace").splitlines()):
        if not line.startswith("exit:"):
            continue
        _, _, raw = line.partition(":")
        try:
            return int(raw.strip())
        except ValueError:
            return None
    return None


def count_value(counts: dict[str, int] | None, severity: str) -> int | None:
    if counts is None:
        return None
    return counts[severity]


def sort_count(value: object) -> int:
    return value if isinstance(value, int) else -1


def fmt_count_pair(errors: int | None, warnings: int | None) -> str:
    if errors is None or warnings is None:
        return "n/a"
    return f"{errors}/{warnings}"


def fmt_graph_shape(row: dict) -> str:
    values = (row["caps"], row["ins"], row["outs"], row["edges"])
    if any(v is None for v in values):
        return "n/a"
    return "/".join(str(v) for v in values)


def collect_rows(batch_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for repo_dir in sorted(batch_dir.iterdir()):
        if not repo_dir.is_dir():
            continue
        for skill_dir in sorted(repo_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            status_file = skill_dir / "STATUS"
            if not status_file.is_file():
                continue
            if status_file.read_text().strip() not in {"phase-a-ok"}:
                continue

            meta = read_meta(skill_dir)
            symbolic_report, symbolic_status = load_json_report(skill_dir / "01-symbolic.json")
            strict_report, strict_status = load_json_report(skill_dir / "02-strict-vscode.json")
            graph_report, graph_status = load_json_report(skill_dir / "03-graph-analyze.json")
            graph_extract, graph_extract_status = load_json_report(skill_dir / "04-graph-extracted.json")

            symbolic = severity_counts(symbolic_report)
            strict = severity_counts(strict_report)
            graph_diag = severity_counts(graph_report)
            caps, ins, outs, edges = graph_shape(graph_extract)

            phase_b_done = (skill_dir / "PHASE_B_STATUS").is_file() and (
                (skill_dir / "PHASE_B_STATUS").read_text().strip() == "phase-b-ok"
            )
            crit_report, crit_status = load_json_report(skill_dir / "08-critique-report.json")
            gr_agent_report, gr_agent_status = load_json_report(skill_dir / "09-graph-agent-report.json")
            full_report, full_status = load_json_report(skill_dir / "10-full-pipeline.json")

            crit = severity_counts(crit_report)
            gr_agent = severity_counts(gr_agent_report)
            full = severity_counts(full_report)

            rows.append(
                {
                    "repo": repo_dir.name,
                    "skill": skill_dir.name,
                    "sha": meta.get("sha", ""),
                    "phase_b_done": int(phase_b_done),
                    "sym_status": symbolic_status,
                    "sym_exit": read_exit_code(skill_dir / "01-symbolic.txt"),
                    "sym_err": count_value(symbolic, "error"),
                    "sym_warn": count_value(symbolic, "warning"),
                    "strict_status": strict_status,
                    "strict_exit": read_exit_code(skill_dir / "02-strict-vscode.txt"),
                    "strict_err": count_value(strict, "error"),
                    "strict_warn": count_value(strict, "warning"),
                    "graph_status": graph_status,
                    "graph_exit": read_exit_code(skill_dir / "03-graph-analyze.txt"),
                    "graph_err": count_value(graph_diag, "error"),
                    "graph_warn": count_value(graph_diag, "warning"),
                    "graph_warning_rules": format_rule_counts(rule_counts(graph_report, "warning")),
                    "extract_status": graph_extract_status,
                    "caps": caps,
                    "ins": ins,
                    "outs": outs,
                    "edges": edges,
                    "crit_status": crit_status,
                    "crit_exit": read_exit_code(skill_dir / "08-critique-report.txt"),
                    "crit_err": count_value(crit, "error"),
                    "crit_warn": count_value(crit, "warning"),
                    "crit_error_rules": format_rule_counts(rule_counts(crit_report, "error")),
                    "gr_agent_status": gr_agent_status,
                    "gr_agent_exit": read_exit_code(skill_dir / "09-graph-agent-report.txt"),
                    "gr_agent_err": count_value(gr_agent, "error"),
                    "gr_agent_warn": count_value(gr_agent, "warning"),
                    "full_status": full_status,
                    "full_exit": read_exit_code(skill_dir / "10-full-pipeline.txt"),
                    "full_err": count_value(full, "error"),
                    "full_warn": count_value(full, "warning"),
                    "full_error_rules": format_rule_counts(rule_counts(full_report, "error")),
                }
            )
    return rows


def write_csv(rows: list[dict], batch_dir: Path) -> Path:
    csv_path = batch_dir / "summary.csv"
    if not rows:
        csv_path.write_text("")
        return csv_path
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def write_findings(rows: list[dict], batch_dir: Path) -> Path:
    md = batch_dir / "findings.md"
    lines = [f"# {batch_dir.name} findings", ""]
    lines.append(f"Skills evaluated: {len(rows)}")
    phase_b_count = sum(r["phase_b_done"] for r in rows)
    lines.append(f"Phase B (agent-mode) complete on: {phase_b_count}/{len(rows)}")
    incomplete = [r for r in rows if not r["phase_b_done"]]
    if incomplete:
        lines.append(
            "Phase B incomplete on: "
            + ", ".join(f"{r['repo']}/{r['skill']}" for r in incomplete)
        )
    lines.append("")
    lines.append("## All skills, ranked by full-pipeline error count")
    lines.append("")
    lines.append(
        "| Repo | Skill | Phase B | Sym E/W | Strict E/W | Graph E/W | "
        "Caps/I/O/E | Crit E/W | Agent Graph E/W | Full E/W |"
    )
    lines.append(
        "|------|-------|---------|---------|------------|-----------|"
        "------------|----------|-----------------|----------|"
    )
    ranked = sorted(
        rows,
        key=lambda r: (
            sort_count(r["full_err"]),
            sort_count(r["crit_err"]),
            sort_count(r["sym_err"]),
        ),
        reverse=True,
    )
    for r in ranked:
        lines.append(
            f"| {r['repo']} | {r['skill']} | "
            f"{'done' if r['phase_b_done'] else 'pending'} | "
            f"{fmt_count_pair(r['sym_err'], r['sym_warn'])} | "
            f"{fmt_count_pair(r['strict_err'], r['strict_warn'])} | "
            f"{fmt_count_pair(r['graph_err'], r['graph_warn'])} | "
            f"{fmt_graph_shape(r)} | "
            f"{fmt_count_pair(r['crit_err'], r['crit_warn'])} | "
            f"{fmt_count_pair(r['gr_agent_err'], r['gr_agent_warn'])} | "
            f"{fmt_count_pair(r['full_err'], r['full_warn'])} |"
        )
    lines.append("")
    lines.append("## Report integrity")
    lines.append("")
    status_keys = [
        ("symbolic", "sym_status"),
        ("strict", "strict_status"),
        ("heuristic graph", "graph_status"),
        ("graph extract", "extract_status"),
        ("critique", "crit_status"),
        ("agent graph", "gr_agent_status"),
        ("full pipeline", "full_status"),
    ]
    problems: list[str] = []
    for r in rows:
        for label, key in status_keys:
            status = r[key]
            if status == "ok":
                continue
            if not r["phase_b_done"] and key in {"crit_status", "gr_agent_status", "full_status"}:
                continue
            problems.append(f"- **{r['repo']}/{r['skill']}**: {label} JSON is {status}")
    if problems:
        lines.extend(problems)
    else:
        lines.append("_All expected JSON reports loaded successfully._")
    lines.append("")
    lines.append("## Headline findings (Phase B done, errors > 0)")
    lines.append("")
    headline = [
        r for r in ranked if r["phase_b_done"] and isinstance(r["full_err"], int) and r["full_err"] > 0
    ]
    if not headline:
        lines.append("_None yet. Either Phase B incomplete or all skills passed cleanly._")
    else:
        for r in headline:
            lines.append(
                f"- **{r['repo']}/{r['skill']}**: "
                f"{r['full_err']} errors, {r['full_warn']} warnings in full pipeline. "
                f"Exit code: {r['full_exit']}. "
                f"Critique alone: {r['crit_err']} errors. "
                f"Symbolic: {r['sym_err']} errors. "
                f"Error rules: {r['full_error_rules'] or 'none'}."
            )
    lines.append("")
    md.write_text("\n".join(lines) + "\n")
    return md


def main(batch_dir: Path | None = None) -> None:
    if batch_dir is None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("batch_dir", type=Path, help="Batch artifact directory to summarize.")
        args = parser.parse_args()
        batch_dir = args.batch_dir

    rows = collect_rows(batch_dir)
    csv_path = write_csv(rows, batch_dir)
    md_path = write_findings(rows, batch_dir)
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    print(f"Skills counted: {len(rows)}")
    print(f"Phase B complete: {sum(r['phase_b_done'] for r in rows)}")


if __name__ == "__main__":
    main()
