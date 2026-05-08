from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skillcheck import __version__
from skillcheck import config as runtime_config
from skillcheck.config_loader import ConfigError, find_config, load_config
from skillcheck.core import (
    append_run,
    build_entry,
    check_regression,
    extract_graph_agent,
    extract_graph_heuristic,
    generate_activation_hypotheses,
    ingest_critique_response,
    ledger_path_for,
    load_ledger,
    merge_critique_diagnostics,
    merge_diagnostics,
    render_critique_prompt,
    render_activation_json,
    render_activation_markdown,
    render_activation_text,
    render_graph_json,
    render_graph_text,
    render_ledger_json,
    render_ledger_text,
    run_divergence_analyzers,
    run_graph_analyzers,
    validate,
    LedgerError,
    RunAgents,
    ValidationModes,
)
from skillcheck.agents import get_graph_prompt
from skillcheck.agents.graph_parser import GraphParseError
from skillcheck.agents.parser import CritiqueParseError
from skillcheck.parser import parse as _parse_skill
from skillcheck.result import Diagnostic, Severity, ValidationResult

# ---------------------------------------------------------------------------
# ANSI helpers (zero dependencies)
# ---------------------------------------------------------------------------

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"

_SEV_SYMBOL = {Severity.ERROR: "✗", Severity.WARNING: "⚠", Severity.INFO: "·"}
_SEV_COLOR = {Severity.ERROR: _RED, Severity.WARNING: _YELLOW, Severity.INFO: _DIM}


def _style(text: str, *codes: str, color: bool = True) -> str:
    """Wrap *text* in ANSI escape codes when *color* is enabled."""
    if not color:
        return text
    return "".join(codes) + text + _RESET


# ---------------------------------------------------------------------------
# Path collection
# ---------------------------------------------------------------------------


def _collect_paths(target: Path) -> list[Path]:
    """Return a list of SKILL.md files to validate.

    For a directory, recursively finds all files named exactly 'SKILL.md'.
    For a file, returns it directly without name filtering.
    """
    if target.is_dir():
        return sorted(target.rglob("SKILL.md"))
    return [target]


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _format_text(
    results: list[ValidationResult],
    *,
    color: bool = False,
    critique_source: str | None = None,
    graph_source: str | None = None,
) -> str:
    lines: list[str] = []
    if critique_source is not None:
        lines.append(f"Critique source: {critique_source}")
    if graph_source is not None:
        lines.append(f"Graph source: {graph_source}")
    for result in results:
        if result.valid:
            tag = _style("✔ PASS", _BOLD, _GREEN, color=color)
        else:
            tag = _style("✗ FAIL", _BOLD, _RED, color=color)
        lines.append(f"{tag}  {result.path}")

        for d in result.diagnostics:
            sym = _SEV_SYMBOL.get(d.severity, "·")
            sev_col = _SEV_COLOR.get(d.severity, "")
            loc = f"line {d.line}" if d.line is not None else ""
            sev_label = _style(f"{sym} {d.severity.value}", sev_col, color=color)
            rule = _style(d.rule, _DIM, color=color)
            lines.append(f"  {loc:>8}  {sev_label:<18s}  {rule}  {d.message}")
            if d.context:
                ctx = _style(d.context, _DIM, color=color)
                lines.append(f"{'':>12}  {ctx}")

    # summary
    total = len(results)
    passed = sum(1 for r in results if r.valid)
    failed = total - passed
    warn_count = sum(
        1 for r in results for d in r.diagnostics if d.severity == Severity.WARNING
    )
    noun = "file" if total == 1 else "files"

    parts = [
        _style(f"{passed} passed", _GREEN, color=color),
        _style(f"{failed} failed", _RED, color=color) if failed else f"{failed} failed",
    ]
    if warn_count:
        w = f"{warn_count} warning{'s' if warn_count != 1 else ''}"
        parts.append(_style(w, _YELLOW, color=color))

    lines.append(f"\nChecked {total} {noun}: {', '.join(parts)}")
    return "\n".join(lines)


def _format_json(
    results: list[ValidationResult],
    version: str,
    critique_source: str | None = None,
    graph_source: dict | None = None,
) -> str:
    passed = sum(1 for r in results if r.valid)
    payload: dict[str, object] = {
        "version": version,
        "files_checked": len(results),
        "files_passed": passed,
        "files_failed": len(results) - passed,
        **(({"critique_source": critique_source}) if critique_source is not None else {}),
        **(({"graph_source": graph_source}) if graph_source is not None else {}),
        "results": [
            {
                "path": str(r.path),
                "valid": r.valid,
                "diagnostics": [
                    {
                        "rule": d.rule,
                        "severity": d.severity.value,
                        "message": d.message,
                        "line": d.line,
                        "context": d.context,
                        "source": d.source,
                        "confidence": d.confidence,
                    }
                    for d in r.diagnostics
                ],
            }
            for r in results
        ],
    }
    return json.dumps(payload, indent=2)


def _format_markdown(
    results: list[ValidationResult],
    *,
    critique_source: str | None = None,
    graph_source: str | None = None,
) -> str:
    lines: list[str] = ["# skillcheck report", ""]
    if critique_source is not None:
        lines.append(f"Critique source: `{critique_source}`")
        lines.append("")
    if graph_source is not None:
        lines.append(f"Graph source: `{graph_source}`")
        lines.append("")

    total = len(results)
    passed = sum(1 for r in results if r.valid)
    failed = total - passed
    warnings = sum(1 for r in results for d in r.diagnostics if d.severity == Severity.WARNING)
    lines.extend([
        f"Checked `{total}` file{'s' if total != 1 else ''}: `{passed}` passed, `{failed}` failed, `{warnings}` warnings.",
        "",
    ])

    for result in results:
        status = "PASS" if result.valid else "FAIL"
        lines.append(f"## {status}: {result.path}")
        lines.append("")
        if not result.diagnostics:
            lines.append("No diagnostics.")
            lines.append("")
            continue
        lines.extend([
            "| Line | Severity | Rule | Source | Confidence | Message |",
            "|---:|---|---|---|---|---|",
        ])
        for diagnostic in result.diagnostics:
            line = "" if diagnostic.line is None else str(diagnostic.line)
            message = diagnostic.message.replace("|", "\\|")
            lines.append(
                f"| {line} | {diagnostic.severity.value} | `{diagnostic.rule}` | "
                f"{diagnostic.source} | {diagnostic.confidence} | {message} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def _gha_escape(value: str) -> str:
    """Escape a string for use in GitHub Actions workflow command property values."""
    value = value.replace("%", "%25")
    value = value.replace("\r", "%0D")
    value = value.replace("\n", "%0A")
    value = value.replace(":", "%3A")
    value = value.replace(",", "%2C")
    return value


def _format_github(results: list[ValidationResult]) -> str:
    """Format diagnostics as GitHub Actions workflow commands for PR annotations."""
    severity_map = {
        Severity.ERROR: "error",
        Severity.WARNING: "warning",
        Severity.INFO: "notice",
    }
    lines: list[str] = []
    for result in results:
        filepath = _gha_escape(str(result.path))
        for d in result.diagnostics:
            gh_level = severity_map.get(d.severity, "notice")
            parts = [f"file={filepath}"]
            if d.line is not None:
                parts.append(f"line={d.line}")
            loc = ",".join(parts)
            message = _gha_escape(d.message)
            lines.append(f"::{gh_level} {loc},title=skillcheck: {d.rule}::{message}")
    return "\n".join(lines)


def _format_agent(
    results: list[ValidationResult],
    *,
    critique_source: str | None = None,
    graph_source: str | None = None,
) -> str:
    failing = [result for result in results if not result.valid]
    warnings = [
        diagnostic
        for result in results
        for diagnostic in result.diagnostics
        if diagnostic.severity == Severity.WARNING
    ]
    lines = [
        "skillcheck agent report",
        f"status: {'fail' if failing else 'pass'}",
        f"files_checked: {len(results)}",
        f"files_failed: {len(failing)}",
        f"warnings: {len(warnings)}",
    ]
    if critique_source:
        lines.append(f"critique_source: {critique_source}")
    if graph_source:
        lines.append(f"graph_source: {graph_source}")
    lines.append("")
    lines.append("next_actions:")
    actionable = [
        (result.path, diagnostic)
        for result in results
        for diagnostic in result.diagnostics
        if diagnostic.severity in {Severity.ERROR, Severity.WARNING}
    ]
    if not actionable:
        lines.append("- No blocking or warning diagnostics. Keep the ledger current with --history.")
    else:
        for path, diagnostic in actionable[:20]:
            location = f":{diagnostic.line}" if diagnostic.line else ""
            lines.append(
                f"- Fix {diagnostic.rule} in {path}{location}: {diagnostic.message}"
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

_EPILOG = """\
examples:
  skillcheck SKILL.md                        validate a single file
  skillcheck skills/                          scan a directory recursively
  skillcheck SKILL.md --format json           machine-readable output for CI
  skillcheck SKILL.md --max-lines 800         override sizing thresholds
  skillcheck SKILL.md --ignore frontmatter    suppress a rule category
  skillcheck SKILL.md --min-desc-score 50     require minimum description quality
  skillcheck SKILL.md --target-agent vscode   scope checks to VS Code
  skillcheck SKILL.md --strict-vscode         treat VS Code issues as errors
  skillcheck SKILL.md --target-agent cursor   scope checks to Cursor
  skillcheck SKILL.md --strict-cursor         treat Cursor issues as errors
  skillcheck SKILL.md --strict                treat all warnings as errors (umbrella)
  skillcheck SKILL.md --skip-ref-check        skip file reference validation
  skillcheck SKILL.md --emit-critique-prompt  print prompt for agent self-critique
  skillcheck SKILL.md --ingest-critique r.json  ingest agent response and merge diagnostics
"""

# Delimiter used between prompts when emitting for multiple skills.
_PROMPT_DELIMITER = "# === skillcheck:critique-prompt:{path} ==="

# Delimiter used between graph renders when emitting for multiple skills.
_GRAPH_DELIMITER = "# === skillcheck:graph:{path} ==="

# Delimiter used between graph-extraction prompts when emitting for multiple skills.
_GRAPH_PROMPT_DELIMITER = "# === skillcheck:graph-prompt:{path} ==="


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillcheck",
        description="Cross-agent skill quality gate for SKILL.md files. Validates against the agentskills.io spec.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        nargs="+",
        type=Path,
        help="Path to a SKILL.md file or a directory to scan recursively. Multiple paths accepted.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "md", "agent", "github"],
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=None,
        metavar="N",
        help="Override the line-count threshold (default: 500).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        metavar="N",
        help="Override the token-count threshold (default: 8000).",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        dest="ignore_prefixes",
        metavar="PREFIX",
        default=[],
        help="Suppress rules matching this prefix. Can be repeated.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="Disable colored output.",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        default=False,
        help="Suppress all output. Only the exit code indicates result.",
    )
    parser.add_argument(
        "--skip-dirname-check",
        action="store_true",
        default=False,
        help="Skip directory-name matching check (useful for CI temp paths).",
    )
    parser.add_argument(
        "--skip-ref-check",
        action="store_true",
        default=False,
        help="Skip file reference validation (useful when referenced files are unavailable).",
    )
    parser.add_argument(
        "--min-desc-score",
        type=int,
        default=None,
        metavar="N",
        help="Minimum description quality score (0-100). Below this triggers a warning.",
    )
    parser.add_argument(
        "--target-agent",
        choices=["claude", "vscode", "cursor", "all"],
        default="all",
        help="Scope compatibility checks to a specific agent (default: all).",
    )
    parser.add_argument(
        "--strict-vscode",
        action="store_true",
        default=False,
        help="Promote VS Code compatibility issues to errors.",
    )
    parser.add_argument(
        "--strict-cursor",
        action="store_true",
        default=False,
        help="Promote Cursor compatibility issues to errors.",
    )
    parser.add_argument(
        "--strict",
        dest="strict_all",
        action="store_true",
        default=False,
        help=(
            "Strict mode. Escalates warning-only runs to exit 1, "
            "promotes VS Code compatibility to errors (same as --strict-vscode), "
            "promotes Cursor compatibility to errors (same as --strict-cursor), "
            "and enables the 'all' field in config for future strict rules."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to skillcheck.toml. Defaults to the nearest skillcheck.toml from the target path upward.",
    )
    parser.add_argument(
        "--semantic",
        action="store_true",
        default=False,
        help="Run semantic-adjacent validation. In standalone mode this enables heuristic graph analysis; with ingested agent responses it merges those diagnostics.",
    )
    parser.add_argument(
        "--agent-reason",
        action="store_true",
        default=False,
        help="Agent-native workflow shortcut. Without ingested responses, emits an agent prompt packet and exits 0.",
    )
    parser.add_argument(
        "--emit-critique-prompt",
        action="store_true",
        default=False,
        help=(
            "Print the agent self-critique prompt to stdout and exit 0. "
            "Skips all symbolic validation. Use --format json to wrap in {\"prompt\": \"...\"}."
        ),
    )
    parser.add_argument(
        "--ingest-critique",
        metavar="PATH",
        default=None,
        help=(
            "Read an agent self-critique JSON response from PATH (use - for stdin), "
            "convert to diagnostics, merge with symbolic results, and emit a unified report. "
            "Exit code 3 signals semantic drift when symbolic validation passed."
        ),
    )
    parser.add_argument(
        "--critique-agent",
        choices=["claude", "codex", "cursor"],
        default=None,
        metavar="NAME",
        help=(
            "Agent variant for the self-critique prompt (claude, codex, cursor; default: claude). "
            "Requires --emit-critique-prompt or --ingest-critique."
        ),
    )
    parser.add_argument(
        "--emit-graph",
        action="store_true",
        default=False,
        help=(
            "Print the extracted capability graph to stdout and exit 0. "
            "Replaces the validation report. Use --format json for machine-readable output."
        ),
    )
    parser.add_argument(
        "--analyze-graph",
        action="store_true",
        default=False,
        help=(
            "Extract the capability graph, run graph analyzers, and merge diagnostics "
            "into the validation report. Augments (does not replace) the report."
        ),
    )
    parser.add_argument(
        "--emit-graph-prompt",
        action="store_true",
        default=False,
        help=(
            "Print the graph-extraction prompt to stdout and exit 0. "
            "Hand the output to an agent, then use --ingest-graph with the response. "
            "Mutually exclusive with all other emit and augment modes."
        ),
    )
    parser.add_argument(
        "--ingest-graph",
        metavar="PATH",
        default=None,
        help=(
            "Read an agent graph-extraction JSON response from PATH (use - for stdin), "
            "build a CapabilityGraph, run graph analyzers and divergence analyzers, and "
            "merge all diagnostics into the report. Compatible with --ingest-critique. "
            "Supersedes --analyze-graph (which does heuristic-only analysis)."
        ),
    )
    parser.add_argument(
        "--graph-agent",
        choices=["claude", "codex", "cursor"],
        default=None,
        metavar="NAME",
        help=(
            "Agent variant for the graph-extraction prompt (claude, codex, cursor; default: claude). "
            "Requires --emit-graph-prompt or --ingest-graph."
        ),
    )
    parser.add_argument(
        "--history",
        action="store_true",
        default=False,
        help=(
            "Append a validation record to the per-skill .skillcheck-history.json ledger "
            "next to the SKILL.md file. Off by default. Incompatible with emit modes."
        ),
    )
    parser.add_argument(
        "--show-history",
        action="store_true",
        default=False,
        help=(
            "Print the validation history ledger for the skill and exit 0. "
            "Skips all validation. Use --format json for machine-readable output. "
            "Incompatible with emit modes and with --history."
        ),
    )
    parser.add_argument(
        "--activation-hypotheses",
        action="store_true",
        default=False,
        help=(
            "Experimental emit mode. Generate likely natural-language activation triggers "
            "for the skill and exit 0."
        ),
    )
    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _resolve_paths(args: argparse.Namespace) -> list[Path]:
    """Resolve the target paths to a list of SKILL.md files, exiting on error."""
    all_paths: list[Path] = []
    for target in args.path:
        if not target.exists():
            print(f"Error: path not found: {target}", file=sys.stderr)
            sys.exit(2)
        paths = _collect_paths(target)
        if not paths:
            print(f"No SKILL.md files found under: {target}", file=sys.stderr)
            sys.exit(2)
        all_paths.extend(paths)
    return all_paths


def _do_emit_graph(paths: list[Path], fmt: str) -> None:
    """Print the capability graph for each path and exit 0."""
    multiple = len(paths) > 1
    for path in paths:
        skill = _parse_skill(path)
        graph = extract_graph_heuristic(skill)
        if multiple:
            print(_GRAPH_DELIMITER.format(path=path))
        if fmt == "json":
            print(render_graph_json(graph))
        else:
            print(render_graph_text(graph))


def _do_emit_critique_prompts(paths: list[Path], fmt: str, agent_id: str = "claude") -> None:
    """Print critique prompts to stdout and exit 0."""
    multiple = len(paths) > 1
    for path in paths:
        skill = _parse_skill(path)
        prompt = render_critique_prompt(skill, agent_id=agent_id)
        if multiple:
            print(_PROMPT_DELIMITER.format(path=path))
        if fmt == "json":
            print(json.dumps({"prompt": prompt}))
        elif fmt == "md":
            print(f"# skillcheck critique prompt\n\n```text\n{prompt}\n```")
        elif fmt == "agent":
            print("skillcheck critique prompt")
            print("return_json_only: true")
            print(prompt)
        else:
            print(prompt)


def _read_ingest_raw(ingest_path: str) -> str:
    """Read the raw critique response from PATH or stdin, exiting on error."""
    if ingest_path == "-":
        return sys.stdin.read()
    p = Path(ingest_path)
    if not p.exists():
        print(f"Error: critique response file not found: {p}", file=sys.stderr)
        sys.exit(2)
    try:
        return p.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: cannot read {p}: {exc}", file=sys.stderr)
        sys.exit(2)


def _do_emit_graph_prompts(paths: list[Path], fmt: str, agent_id: str = "claude") -> None:
    """Print graph-extraction prompts to stdout and exit 0."""
    multiple = len(paths) > 1
    for path in paths:
        skill = _parse_skill(path)
        prompt = get_graph_prompt(agent_id).render(skill)
        if multiple:
            print(_GRAPH_PROMPT_DELIMITER.format(path=path))
        if fmt == "json":
            print(json.dumps({"prompt": prompt}))
        elif fmt == "md":
            print(f"# skillcheck graph prompt\n\n```text\n{prompt}\n```")
        elif fmt == "agent":
            print("skillcheck graph prompt")
            print("return_json_only: true")
            print(prompt)
        else:
            print(prompt)


def _do_emit_agent_reason_packet(paths: list[Path], fmt: str, critique_agent: str, graph_agent: str) -> None:
    """Print a combined critique and graph prompt packet for in-agent execution."""
    packets: list[dict[str, str]] = []
    for path in paths:
        skill = _parse_skill(path)
        packets.append({
            "path": str(path),
            "critique_prompt": render_critique_prompt(skill, agent_id=critique_agent),
            "graph_prompt": get_graph_prompt(graph_agent).render(skill),
        })

    if fmt == "json":
        print(json.dumps({"agent_reason": packets}, indent=2))
        return

    for index, packet in enumerate(packets, start=1):
        if len(packets) > 1:
            print(f"# === skillcheck:agent-reason:{packet['path']} ===")
        if fmt == "md":
            print(f"# Agent Reason Packet {index}\n")
            print(f"Path: `{packet['path']}`\n")
            print("## Critique prompt\n")
            print(f"```text\n{packet['critique_prompt']}\n```\n")
            print("## Graph prompt\n")
            print(f"```text\n{packet['graph_prompt']}\n```")
        elif fmt == "agent":
            print("skillcheck agent-reason packet")
            print(f"path: {packet['path']}")
            print("task: run both prompts, save each JSON response, then invoke skillcheck with --ingest-critique and --ingest-graph")
            print("critique_prompt:")
            print(packet["critique_prompt"])
            print("graph_prompt:")
            print(packet["graph_prompt"])
        else:
            print("Critique prompt:")
            print(packet["critique_prompt"])
            print("\nGraph prompt:")
            print(packet["graph_prompt"])


def _do_emit_activation(paths: list[Path], fmt: str) -> None:
    """Print activation hypotheses for each path and exit 0."""
    multiple = len(paths) > 1
    reports = [generate_activation_hypotheses(_parse_skill(path)) for path in paths]
    if fmt == "json":
        if multiple:
            payload = [json.loads(render_activation_json(report)) for report in reports]
            print(json.dumps({"activation_reports": payload}, indent=2))
        else:
            print(render_activation_json(reports[0]))
        return

    for path, report in zip(paths, reports):
        if multiple:
            print(f"# === skillcheck:activation:{path} ===")
        if fmt == "md":
            print(render_activation_markdown(report))
        else:
            print(render_activation_text(report))


def _apply_config(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Apply skillcheck.toml defaults to parsed args."""
    config_path = args.config or find_config(args.path[0])
    try:
        loaded_config = load_config(config_path)
    except ConfigError as exc:
        parser.error(str(exc))

    runtime_config.set_extension_fields(loaded_config.extension_fields)

    if loaded_config.format is not None and args.format == "text":
        args.format = loaded_config.format
    if loaded_config.max_lines is not None and args.max_lines is None:
        args.max_lines = loaded_config.max_lines
    if loaded_config.max_tokens is not None and args.max_tokens is None:
        args.max_tokens = loaded_config.max_tokens
    if loaded_config.min_desc_score is not None and args.min_desc_score is None:
        args.min_desc_score = loaded_config.min_desc_score
    if loaded_config.target_agent is not None and args.target_agent == "all":
        args.target_agent = loaded_config.target_agent
    if loaded_config.strict_vscode is True:
        args.strict_vscode = True
    if loaded_config.strict_cursor is True:
        args.strict_cursor = True
    if loaded_config.strict_all is True:
        args.strict_all = True
    if loaded_config.skip_dirname_check is True:
        args.skip_dirname_check = True
    if loaded_config.skip_ref_check is True:
        args.skip_ref_check = True
    if loaded_config.ignore and not args.ignore_prefixes:
        args.ignore_prefixes = list(loaded_config.ignore)
    if loaded_config.analyze_graph is True:
        args.analyze_graph = True
    if loaded_config.semantic is True:
        args.semantic = True
    if loaded_config.history is True:
        args.history = True
    if loaded_config.critique_agent is not None and args.critique_agent is None:
        args.critique_agent = loaded_config.critique_agent
    if loaded_config.graph_agent is not None and args.graph_agent is None:
        args.graph_agent = loaded_config.graph_agent


def main() -> None:
    # Ensure UTF-8 output on Windows where the default encoding may be cp1252.
    if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    if sys.stderr.encoding and sys.stderr.encoding.lower().replace("-", "") != "utf8":
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    parser = _build_parser()
    args = parser.parse_args()
    _apply_config(args, parser)

    # --strict: enable all strict modes. warnings_as_errors is an internal
    # exit-code flag (no longer a public flag); --strict is the umbrella switch.
    args.warnings_as_errors = False
    if args.strict_all:
        args.warnings_as_errors = True
        args.strict_vscode = True
        args.strict_cursor = True

    if args.format not in {"text", "json", "md", "agent", "github"}:
        parser.error("format must be one of: text, json, md, agent")
    if args.target_agent not in {"claude", "vscode", "cursor", "all"}:
        parser.error("target-agent must be one of: claude, vscode, cursor, all")
    if args.critique_agent is not None and args.critique_agent not in {"claude", "codex", "cursor"}:
        parser.error("critique-agent must be one of: claude, codex, cursor")
    if args.graph_agent is not None and args.graph_agent not in {"claude", "codex", "cursor"}:
        parser.error("graph-agent must be one of: claude, codex, cursor")

    if args.semantic and args.ingest_graph is None:
        args.analyze_graph = True

    # -----------------------------------------------------------------------
    # Mutual exclusion checks
    # -----------------------------------------------------------------------

    if args.emit_critique_prompt and args.ingest_critique is not None:
        print(
            "Cannot use --emit-critique-prompt and --ingest-critique together. "
            "Pick one: emit a prompt for your agent to execute, or ingest the agent's response.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.emit_graph and args.analyze_graph:
        print(
            "Cannot use --emit-graph with --analyze-graph. "
            "--emit-graph is an emit mode (replaces the report). "
            "--analyze-graph is an augment mode (adds to the report).",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.emit_graph and args.emit_critique_prompt:
        print(
            "Cannot use --emit-graph with --emit-critique-prompt. "
            "Both are emit modes; pick one.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.emit_graph and args.ingest_critique is not None:
        print(
            "Cannot use --emit-graph with --ingest-critique. "
            "--emit-graph replaces the report; --ingest-critique augments it.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.emit_graph_prompt and args.emit_graph:
        print(
            "Cannot use --emit-graph-prompt with --emit-graph. "
            "Both are emit modes; pick one.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.emit_graph_prompt and args.emit_critique_prompt:
        print(
            "Cannot use --emit-graph-prompt with --emit-critique-prompt. "
            "Both are emit modes; pick one.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.emit_graph_prompt and args.ingest_critique is not None:
        print(
            "Cannot use --emit-graph-prompt with --ingest-critique. "
            "--emit-graph-prompt is an emit mode; --ingest-critique is an augment mode.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.emit_graph_prompt and args.analyze_graph:
        print(
            "Cannot use --emit-graph-prompt with --analyze-graph. "
            "--emit-graph-prompt is an emit mode; --analyze-graph is an augment mode.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.emit_graph_prompt and args.ingest_graph is not None:
        print(
            "Cannot use --emit-graph-prompt with --ingest-graph. "
            "--emit-graph-prompt emits a prompt; --ingest-graph ingests the agent's response. "
            "Use them in separate invocations.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.ingest_graph is not None and args.emit_graph:
        print(
            "Cannot use --ingest-graph with --emit-graph. "
            "--emit-graph replaces the report; --ingest-graph augments it.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.ingest_graph is not None and args.emit_critique_prompt:
        print(
            "Cannot use --ingest-graph with --emit-critique-prompt. "
            "--emit-critique-prompt is an emit mode; --ingest-graph is an augment mode.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.ingest_graph is not None and args.analyze_graph:
        print(
            "Cannot use --ingest-graph with --analyze-graph. "
            "--ingest-graph supersedes heuristic-only graph analysis.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.agent_reason and (
        args.emit_critique_prompt
        or args.emit_graph
        or args.emit_graph_prompt
        or args.activation_hypotheses
    ):
        print(
            "Cannot use --agent-reason with another emit mode. "
            "Use --agent-reason alone to emit the combined agent prompt packet.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Emit modes incompatible with --history (emit modes skip validation entirely).
    _EMIT_FLAGS = {
        "--emit-critique-prompt": args.emit_critique_prompt,
        "--emit-graph": args.emit_graph,
        "--emit-graph-prompt": args.emit_graph_prompt,
        "--agent-reason": args.agent_reason and args.ingest_critique is None and args.ingest_graph is None,
        "--activation-hypotheses": args.activation_hypotheses,
    }
    for emit_flag, emit_active in _EMIT_FLAGS.items():
        if emit_active and args.history:
            print(
                f"Cannot use --history with {emit_flag}. "
                f"--history records validation runs; emit modes skip validation.",
                file=sys.stderr,
            )
            sys.exit(2)
        if emit_active and args.show_history:
            print(
                f"Cannot use --show-history with {emit_flag}. "
                f"--show-history reads the ledger; {emit_flag} emits a prompt.",
                file=sys.stderr,
            )
            sys.exit(2)

    if args.show_history and args.history:
        print(
            "Cannot use --show-history with --history. "
            "--show-history reads the ledger; --history writes to it. Pick one.",
            file=sys.stderr,
        )
        sys.exit(2)

    agent_id = args.critique_agent or "claude"
    graph_agent_id = args.graph_agent or "claude"

    if args.critique_agent is not None and not args.emit_critique_prompt and not args.agent_reason and args.ingest_critique is None:
        parser.error("--critique-agent requires --emit-critique-prompt or --ingest-critique")

    if args.graph_agent is not None and not args.emit_graph_prompt and not args.agent_reason and args.ingest_graph is None:
        parser.error("--graph-agent requires --emit-graph-prompt or --ingest-graph")

    paths = _resolve_paths(args)

    # --show-history: read the ledger for the first path, print it, and exit.
    # Directory mode is not supported for show-history because each skill has
    # its own ledger; run per-skill instead.
    if args.show_history:
        target_path = paths[0]
        lp = ledger_path_for(target_path)
        if not lp.exists():
            print(
                f"No history ledger found for {target_path}. "
                f"Run 'skillcheck {target_path} --history' to start tracking.",
                file=sys.stderr,
            )
            sys.exit(2)
        try:
            ledger = load_ledger(lp)
        except LedgerError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        if ledger is None:
            print(f"No history ledger found for {target_path}.", file=sys.stderr)
            sys.exit(2)
        if not args.quiet:
            if args.format == "json":
                print(render_ledger_json(ledger))
            else:
                print(render_ledger_text(ledger))
        sys.exit(0)

    # --emit-graph: emit the heuristic graph and skip symbolic validation entirely
    if args.emit_graph:
        _do_emit_graph(paths, fmt=args.format)
        sys.exit(0)

    # --emit-critique-prompt: skip symbolic validation entirely
    if args.emit_critique_prompt:
        _do_emit_critique_prompts(paths, fmt=args.format, agent_id=agent_id)
        sys.exit(0)

    # --emit-graph-prompt: render and print the graph-extraction prompt, then exit
    if args.emit_graph_prompt:
        _do_emit_graph_prompts(paths, fmt=args.format, agent_id=graph_agent_id)
        sys.exit(0)

    if args.agent_reason and args.ingest_critique is None and args.ingest_graph is None:
        _do_emit_agent_reason_packet(paths, args.format, agent_id, graph_agent_id)
        sys.exit(0)

    if args.activation_hypotheses:
        _do_emit_activation(paths, args.format)
        sys.exit(0)

    # Run symbolic validation (always, including when ingesting)
    results = [
        validate(
            p,
            max_lines=args.max_lines,
            max_tokens=args.max_tokens,
            ignore_prefixes=args.ignore_prefixes or None,
            skip_dirname_check=args.skip_dirname_check,
            skip_ref_check=args.skip_ref_check,
            min_desc_score=args.min_desc_score,
            strict_vscode=args.strict_vscode,
            strict_cursor=args.strict_cursor,
            strict_all=args.strict_all,
            target_agent=args.target_agent,
         )
        for p in paths
     ]

    # Track symbolic-only validity BEFORE any ingest merges. Ingest parse
    # failures and symbolic errors both exit 1; semantic-only drift exits 3.
    symbolic_errors_before_ingest = any(not r.valid for r in results)

    critique_source: str | None = None
    graph_source_text: str | None = None
    graph_source_json: dict | None = None
    any_ingest_failed = False

    if args.ingest_critique is not None:
        raw = _read_ingest_raw(args.ingest_critique)

        try:
            first_skill = _parse_skill(paths[0])
            critique_diags = ingest_critique_response(first_skill, raw)
        except CritiqueParseError as exc:
            critique_diags = [
                Diagnostic(
                    rule="semantic.ingest.parse_error",
                    severity=Severity.ERROR,
                    message=str(exc),
                )
            ]
            any_ingest_failed = True

        results = [merge_critique_diagnostics(r, critique_diags) for r in results]
        critique_source = agent_id

    if args.ingest_graph is not None:
        raw_graph = _read_ingest_raw(args.ingest_graph)

        try:
            first_skill = _parse_skill(paths[0])
            agent_graph = extract_graph_agent(first_skill, raw_graph)
            heuristic_graph = extract_graph_heuristic(first_skill)
            agent_graph_diags = run_graph_analyzers(agent_graph)
            divergence_diags = run_divergence_analyzers(agent_graph, heuristic_graph)
            all_graph_diags = agent_graph_diags + divergence_diags
            graph_source_text = f"agent ({graph_agent_id})"
            graph_source_json = {"mode": "agent", "agent": graph_agent_id}
        except GraphParseError as exc:
            all_graph_diags = [
                Diagnostic(
                    rule="semantic.ingest.graph_parse_error",
                    severity=Severity.ERROR,
                    message=str(exc),
                )
            ]
            any_ingest_failed = True

        for i, result in enumerate(results):
            results[i] = merge_diagnostics(result, all_graph_diags)

    elif args.analyze_graph:
        for i, (path, result) in enumerate(zip(paths, results)):
            skill = _parse_skill(path)
            graph = extract_graph_heuristic(skill)
            graph_diags = run_graph_analyzers(graph)
            results[i] = merge_diagnostics(result, graph_diags)
        graph_source_text = "heuristic"
        graph_source_json = {"mode": "heuristic"}

    # Determine exit code based on current results (before history processing).
    # Exit 1: symbolic rules failed before any ingest, or an ingest parse failed.
    if symbolic_errors_before_ingest or any_ingest_failed:
        final_exit_code = 1
    elif any(
        d.severity == Severity.ERROR
        for r in results
        for d in r.diagnostics
        if d.rule.startswith("semantic.")
    ):
        # Exit 3: symbolic passed, all parses succeeded, but a critique ingest added a
        # semantic-namespace contradiction (semantic.*).
        final_exit_code = 3
    elif any(not r.valid for r in results):
        # Exit 1: any remaining errors (e.g. graph.contradiction from agent ingest).
        final_exit_code = 1
    elif any(
        d.severity == Severity.WARNING
        for r in results
        for d in r.diagnostics
    ):
        # Warning-only runs are a clean pass by default; --warnings-as-errors
        # escalates them to exit 1 for stricter CI gates. Exit 2 stays
        # reserved for tool-misuse / input errors so CI can distinguish them.
        final_exit_code = 1 if args.warnings_as_errors else 0
    else:
        final_exit_code = 0

    # --history: run regression check against prior runs, then append the ledger entry.
    # This must happen BEFORE the final print so regression diagnostics appear in output.
    if args.history and len(paths) == 1:
        skill_for_history = _parse_skill(paths[0])
        modes = ValidationModes(
            symbolic=True,
            critique=args.ingest_critique is not None,
            graph=args.ingest_graph is not None or args.analyze_graph,
        )
        run_agents = RunAgents(
            critique_agent=agent_id if args.ingest_critique is not None else None,
            graph_agent=graph_agent_id if args.ingest_graph is not None else None,
        )
        # Preliminary entry: used only to evaluate regression against prior runs.
        preliminary_entry = build_entry(
            skill_for_history,
            results[0],
            modes,
            run_agents,
            final_exit_code,
            __version__,
        )
        lp = ledger_path_for(paths[0])
        try:
            prior_ledger = load_ledger(lp)
            prior_runs = prior_ledger.runs if prior_ledger is not None else ()
            regression_diags = check_regression(prior_runs, preliminary_entry)
        except LedgerError as exc:
            regression_diags = [
                Diagnostic(
                    rule="history.read.failed",
                    severity=Severity.WARNING,
                    message=f"Could not read history ledger: {exc}",
                )
            ]
        if regression_diags:
            results[0] = merge_diagnostics(results[0], regression_diags)
            # Regression is WARNING; does not raise or change the exit code.

        # Build final entry with all diagnostics included (regression if any).
        final_entry = build_entry(
            skill_for_history,
            results[0],
            modes,
            run_agents,
            final_exit_code,
            __version__,
        )
        try:
            append_run(lp, skill_for_history, final_entry)
        except LedgerError as exc:
            results[0] = merge_diagnostics(results[0], [
                Diagnostic(
                    rule="history.write.failed",
                    severity=Severity.WARNING,
                    message=f"Could not write history ledger to {lp}: {exc}",
                )
            ])
            # Write failure is a warning; validation exit code stands.

    # Print report (after history processing so regression/write-fail diagnostics appear).
    if not args.quiet:
        if args.format == "json":
            print(_format_json(
                results,
                __version__,
                critique_source=critique_source,
                graph_source=graph_source_json,
            ))
        elif args.format == "md":
            print(_format_markdown(
                results,
                critique_source=critique_source,
                graph_source=graph_source_text,
            ))
        elif args.format == "agent":
            print(_format_agent(
                results,
                critique_source=critique_source,
                graph_source=graph_source_text,
            ))
        elif args.format == "github":
            print(_format_github(results))
        else:
            use_color = not args.no_color and sys.stdout.isatty()
            print(_format_text(
                results,
                color=use_color,
                critique_source=critique_source,
                graph_source=graph_source_text,
            ))

    sys.exit(final_exit_code)
