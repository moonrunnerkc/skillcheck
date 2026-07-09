#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml

REPO_URL = "https://github.com/anthropics/skills.git"
EXPECTED_VERSION = "skillcheck 1.1.0"
WORKSPACE = Path(__file__).resolve().parents[1]
CORPUS = WORKSPACE / "anthropics-skills"
SKILLCHECK = Path(
    os.environ.get(
        "SKILLCHECK_BIN",
        "/tmp/skillcheck-case-study-v1.1.0-venv/bin/skillcheck",
    )
)
RESULTS_JSON = CORPUS / "skillcheck-results.json"


@dataclass
class CommandResult:
    command: str
    stdout: str
    stderr: str
    exit_code: int


def run_command(args: list[str], cwd: Path) -> CommandResult:
    proc = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    return CommandResult(shell_join(args), proc.stdout, proc.stderr, proc.returncode)


def run_shell(command: str, cwd: Path) -> CommandResult:
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        shell=True,
        capture_output=True,
    )
    return CommandResult(command, proc.stdout, proc.stderr, proc.returncode)


def shell_join(args: Iterable[str]) -> str:
    return " ".join(shell_quote(str(arg)) for arg in args)


def shell_quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:=@%+,-]+", value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def fence(text: str, language: str = "text") -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    ticks = "`" * max(3, longest + 1)
    if text and not text.endswith("\n"):
        text += "\n"
    return f"{ticks}{language}\n{text}{ticks}\n"


def emit_command_block(lines: list[str], result: CommandResult, language: str = "text") -> None:
    lines.append("Command:")
    lines.append(fence(result.command, "shell").rstrip())
    lines.append(f"Exit code: `{result.exit_code}`")
    lines.append("stdout:")
    lines.append(fence(result.stdout, language).rstrip())
    if result.stderr:
        lines.append("stderr:")
        lines.append(fence(result.stderr, "text").rstrip())


def first_n_lines(text: str, count: int) -> str:
    return "".join(text.splitlines(keepends=True)[:count])


def load_results() -> dict[str, Any]:
    with RESULTS_JSON.open("r", encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)
        return data


def iter_diagnostics(data: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for result in data.get("results", []):
        path = result.get("path", "")
        for diagnostic in result.get("diagnostics", []):
            yield path, diagnostic


def parse_first_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text)
    if not match:
        return None
    return int(match.group(1))


def parse_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            raw = "\n".join(lines[1:index])
            parsed = yaml.safe_load(raw) or {}
            if isinstance(parsed, dict):
                return parsed
            return {}
    return {}


def exact_percentage(count: int, total: int) -> str:
    if total == 0:
        return "0%"
    value = Fraction(count * 100, total)
    if value.denominator == 1:
        return f"{value.numerator}%"
    return f"{value.numerator}/{value.denominator}%"


def main() -> int:
    if not CORPUS.exists():
        print(f"missing corpus directory: {CORPUS}", file=sys.stderr)
        return 2

    date_run = datetime.now().astimezone().isoformat(timespec="seconds")

    version_result = run_command([str(SKILLCHECK), "--version"], WORKSPACE)
    version_text = version_result.stdout.strip()
    if version_text != EXPECTED_VERSION:
        print(version_text)
        return 2

    git_sha = run_command(["git", "rev-parse", "HEAD"], CORPUS)
    git_date = run_command(["git", "log", "-1", "--format=%cI"], CORPUS)
    skill_files = run_shell("find . -name SKILL.md | sort", CORPUS)
    skill_file_lines = [line for line in skill_files.stdout.splitlines() if line]

    with RESULTS_JSON.open("w", encoding="utf-8") as output:
        main_proc = subprocess.run(
            [str(SKILLCHECK), ".", "--format", "json"],
            cwd=CORPUS,
            text=True,
            stdout=output,
            stderr=subprocess.PIPE,
        )
    main_command = f"{shell_quote(str(SKILLCHECK))} . --format json > skillcheck-results.json"
    main_validation = CommandResult(main_command, "", main_proc.stderr, main_proc.returncode)

    data = load_results()

    feature_activation = run_command(
        [str(SKILLCHECK), "skills/pptx/SKILL.md", "--activation-hypotheses", "--format", "json"],
        CORPUS,
    )
    feature_critique = run_command(
        [str(SKILLCHECK), "skills/canvas-design/SKILL.md", "--emit-critique-prompt"],
        CORPUS,
    )
    feature_graph_analyze = run_command(
        [str(SKILLCHECK), "skills/docx/SKILL.md", "--analyze-graph", "--format", "json"],
        CORPUS,
    )
    feature_graph_emit = run_command(
        [str(SKILLCHECK), "skills/docx/SKILL.md", "--emit-graph", "--format", "json"],
        CORPUS,
    )
    feature_history = run_command(
        [str(SKILLCHECK), "skills/pptx/SKILL.md", "--history"],
        CORPUS,
    )
    history_files = sorted(CORPUS.glob("**/.skillcheck-history.json"))
    history_file_contents = []
    for history_file in history_files:
        history_file_contents.append(
            (
                history_file.relative_to(CORPUS).as_posix(),
                history_file.read_text(encoding="utf-8"),
            )
        )
    feature_show_history = run_command(
        [str(SKILLCHECK), "skills/pptx/SKILL.md", "--show-history", "--format", "json"],
        CORPUS,
    )

    severity: Counter[str] = Counter()
    rules: Counter[str] = Counter()
    errors = []
    metadata_budget = []
    line_cap: list[tuple[str, int | None]] = []
    body_budget_by_file: dict[str, list[tuple[str, int]]] = {}

    for path, diagnostic in iter_diagnostics(data):
        rule = diagnostic.get("rule", "")
        severity_value = diagnostic.get("severity", "")
        message = diagnostic.get("message", "")
        severity[severity_value] += 1
        rules[rule] += 1

        if severity_value == "error":
            errors.append((path, rule, message))

        if rule == "disclosure.metadata-budget":
            estimate = parse_first_int(r"Frontmatter uses ~(\d+) tokens", message)
            metadata_budget.append((path, estimate))

        if rule == "sizing.body.line-count":
            line_count = parse_first_int(r"got (\d+) lines", message)
            line_cap.append((path, line_count))

        if rule in {"disclosure.body-budget", "sizing.body.token-estimate"}:
            estimate = (
                parse_first_int(r"estimated (\d+) tokens", message)
                or parse_first_int(r"Body uses ~(\d+) tokens", message)
            )
            if estimate is not None and estimate > 8000:
                body_budget_by_file.setdefault(path, []).append((rule, estimate))

    skill_paths = sorted(CORPUS.rglob("SKILL.md"))
    license_paths = []
    for skill_path in skill_paths:
        frontmatter = parse_frontmatter(skill_path)
        if "license" in frontmatter:
            license_paths.append("./" + skill_path.relative_to(CORPUS).as_posix())

    lines: list[str] = []
    lines.append("# skillcheck v1.1.0 case study: anthropics/skills")
    lines.append("")
    lines.append("## Methodology")
    lines.append(f"Date run: `{date_run}`")
    lines.append(f"skillcheck version: `{version_text}`")
    lines.append(f"repo URL: `{REPO_URL}`")
    lines.append(f"commit SHA: `{git_sha.stdout.strip()}`")
    lines.append(f"commit date: `{git_date.stdout.strip()}`")
    lines.append(f"file count: `{len(skill_file_lines)}`")
    lines.append(f"main validation command: `{main_validation.command}`")
    lines.append("")
    lines.append("skillcheck --version output:")
    lines.append(fence(version_result.stdout).rstrip())
    lines.append("git rev-parse HEAD output:")
    lines.append(fence(git_sha.stdout).rstrip())
    lines.append("git log -1 --format=%cI output:")
    lines.append(fence(git_date.stdout).rstrip())
    lines.append("find . -name SKILL.md | sort output:")
    lines.append(fence(skill_files.stdout).rstrip())
    if skill_files.stderr:
        lines.append("find . -name SKILL.md | sort stderr:")
        lines.append(fence(skill_files.stderr).rstrip())
    if main_validation.stderr:
        lines.append("main validation stderr:")
        lines.append(fence(main_validation.stderr).rstrip())
    lines.append("")

    lines.append("## Headline numbers")
    lines.append(f"files_checked: `{data.get('files_checked')}`")
    lines.append(f"files_passed: `{data.get('files_passed')}`")
    lines.append(f"files_failed: `{data.get('files_failed')}`")
    lines.append(f"exit code: `{main_validation.exit_code}`")
    lines.append(f"error count: `{severity['error']}`")
    lines.append(f"warning count: `{severity['warning']}`")
    lines.append(f"info count: `{severity['info']}`")
    lines.append("")

    lines.append("## Rule frequency")
    lines.append("| count | rule ID |")
    lines.append("|---:|---|")
    for rule, count in sorted(rules.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {count} | `{rule}` |")
    lines.append("")

    lines.append("## Failing files")
    failing_files = [result.get("path", "") for result in data.get("results", []) if not result.get("valid")]
    for path in failing_files:
        lines.append(f"- `{path}`")
    lines.append("")

    lines.append("## Errors in detail")
    for path, rule, message in errors:
        lines.append(f"- file path: `{path}`")
        lines.append(f"  rule ID: `{rule}`")
        lines.append("  message:")
        lines.append(fence(message).rstrip())
    lines.append("")

    lines.append("## license field drift")
    lines.append(f"count: `{len(license_paths)}`")
    lines.append(f"total: `{len(skill_paths)}`")
    lines.append(f"percentage: `{exact_percentage(len(license_paths), len(skill_paths))}`")
    for path in license_paths:
        lines.append(f"- `{path}`")
    lines.append("")

    lines.append("## Body token budget violations")
    for path in sorted(body_budget_by_file):
        values = "; ".join(f"{rule}={estimate}" for rule, estimate in body_budget_by_file[path])
        lines.append(f"- `{path}`: {values}")
    lines.append("")

    lines.append("## Body line cap violations")
    for path, line_count in sorted(line_cap):
        lines.append(f"- `{path}`: {line_count}")
    lines.append("")

    lines.append("## Metadata token budget violations")
    lines.append(f"count: `{len(metadata_budget)}`")
    for path, estimate in sorted(metadata_budget):
        lines.append(f"- `{path}`: {estimate}")
    lines.append("")

    lines.append("## v1.1.0 feature outputs (raw)")
    lines.append("### Activation hypotheses (skills/pptx)")
    emit_command_block(lines, feature_activation, "json")
    lines.append("")

    lines.append("### Self-critique prompt schema (skills/canvas-design, first 60 lines)")
    critique_first_60 = CommandResult(
        feature_critique.command,
        first_n_lines(feature_critique.stdout, 60),
        feature_critique.stderr,
        feature_critique.exit_code,
    )
    emit_command_block(lines, critique_first_60, "text")
    lines.append("")

    lines.append("### Capability graph analyze (skills/docx)")
    emit_command_block(lines, feature_graph_analyze, "json")
    lines.append("")

    lines.append("### Capability graph emit (skills/docx)")
    emit_command_block(lines, feature_graph_emit, "json")
    lines.append("")

    lines.append("### History ledger write + read back (skills/pptx)")
    lines.append("History write:")
    emit_command_block(lines, feature_history, "text")
    lines.append(f"History file exists: `{bool(history_files)}`")
    for path, content in history_file_contents:
        lines.append(f"History file path: `{path}`")
        lines.append("History file contents:")
        lines.append(fence(content, "json").rstrip())
    lines.append("History read back:")
    emit_command_block(lines, feature_show_history, "json")
    lines.append("")

    lines.append("## Reproduction")
    lines.append(fence(f"python3 -m venv /tmp/skillcheck-case-study-v1.1.0-venv && /tmp/skillcheck-case-study-v1.1.0-venv/bin/pip install skillcheck==1.1.0\n"
                       f"git clone --depth 1 {REPO_URL} anthropics-skills\n"
                       f"cd anthropics-skills && /tmp/skillcheck-case-study-v1.1.0-venv/bin/skillcheck . --format json > skillcheck-results.json\n"
                       f"SKILLCHECK_BIN=/tmp/skillcheck-case-study-v1.1.0-venv/bin/skillcheck /tmp/skillcheck-case-study-v1.1.0-venv/bin/python {WORKSPACE / 'scripts/skillcheck_case_study_report.py'} > {WORKSPACE / 'skillcheck-case-study-findings.md'}",
                       "shell").rstrip())

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
