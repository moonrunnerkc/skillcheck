from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skillcheck import __version__
from skillcheck.core import (
    extract_graph_agent,
    extract_graph_heuristic,
    ingest_critique_response,
    merge_critique_diagnostics,
    merge_diagnostics,
    render_critique_prompt,
    render_graph_json,
    render_graph_text,
    run_divergence_analyzers,
    run_graph_analyzers,
    validate,
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
                    }
                    for d in r.diagnostics
                ],
            }
            for r in results
        ],
    }
    return json.dumps(payload, indent=2)


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
        type=Path,
        help="Path to a SKILL.md file or a directory to scan recursively.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
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
        choices=["claude", "vscode", "all"],
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
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
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
    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _resolve_paths(args: argparse.Namespace) -> list[Path]:
    """Resolve the target path to a list of SKILL.md files, exiting on error."""
    target: Path = args.path
    if not target.exists():
        print(f"Error: path not found: {target}", file=sys.stderr)
        sys.exit(2)
    paths = _collect_paths(target)
    if not paths:
        print(f"No SKILL.md files found under: {target}", file=sys.stderr)
        sys.exit(2)
    return paths


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
        else:
            print(prompt)


def main() -> None:
    # Ensure UTF-8 output on Windows where the default encoding may be cp1252.
    if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    if sys.stderr.encoding and sys.stderr.encoding.lower().replace("-", "") != "utf8":
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    parser = _build_parser()
    args = parser.parse_args()

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

    agent_id = args.critique_agent or "claude"
    graph_agent_id = args.graph_agent or "claude"

    if args.critique_agent is not None and not args.emit_critique_prompt and args.ingest_critique is None:
        parser.error("--critique-agent requires --emit-critique-prompt or --ingest-critique")

    if args.graph_agent is not None and not args.emit_graph_prompt and args.ingest_graph is None:
        parser.error("--graph-agent requires --emit-graph-prompt or --ingest-graph")

    paths = _resolve_paths(args)

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

    if not args.quiet:
        if args.format == "json":
            print(_format_json(
                results,
                __version__,
                critique_source=critique_source,
                graph_source=graph_source_json,
            ))
        else:
            use_color = not args.no_color and sys.stdout.isatty()
            print(_format_text(
                results,
                color=use_color,
                critique_source=critique_source,
                graph_source=graph_source_text,
            ))

    # Exit 1: symbolic rules failed before any ingest, or an ingest parse failed.
    if symbolic_errors_before_ingest or any_ingest_failed:
        sys.exit(1)

    # Exit 3: symbolic passed, all parses succeeded, but a critique ingest added a
    # semantic-namespace contradiction (semantic.*). Check before general invalidity.
    if any(
        d.severity == Severity.ERROR
        for r in results
        for d in r.diagnostics
        if d.rule.startswith("semantic.")
    ):
        sys.exit(3)

    # Exit 1: any remaining errors (e.g. graph.contradiction from agent ingest).
    if any(not r.valid for r in results):
        sys.exit(1)

    sys.exit(0)
