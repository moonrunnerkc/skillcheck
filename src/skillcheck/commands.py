"""Command execution for the skillcheck CLI.

`cli.py` owns argument wiring (parser construction, config application, dispatch).
This module owns what each mode does: collecting paths, reading ingest payloads,
emitting prompts and graphs, printing the history ledger, and running the default
validation pipeline. The functions here carry their own exit codes via
`sys.exit`, matching the behavior they had when they lived in `cli.py`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from skillcheck import __version__
from skillcheck.agents import get_graph_prompt
from skillcheck.agents._ingest import MAX_INGEST_BYTES
from skillcheck.agents.graph_parser import GraphParseError
from skillcheck.agents.parser import CritiqueParseError
from skillcheck.core import (
    LedgerError,
    RunAgents,
    ValidationModes,
    append_run,
    build_entry,
    check_regression,
    extract_graph_agent,
    extract_graph_heuristic,
    generate_activation_hypotheses,
    ingest_critique_response,
    ledger_path_for,
    load_ledger,
    merge_diagnostics,
    render_activation_json,
    render_activation_markdown,
    render_activation_text,
    render_critique_prompt,
    render_graph_json,
    render_graph_text,
    render_ledger_json,
    render_ledger_text,
    run_divergence_analyzers,
    run_graph_analyzers,
    validate,
)
from skillcheck.formatters import (
    _format_agent,
    _format_github,
    _format_json,
    _format_markdown,
    _format_text,
)
from skillcheck.parser import ParsedSkill, ParseError
from skillcheck.parser import parse as _parse_skill
from skillcheck.result import Diagnostic, Severity, ValidationResult

# Delimiter used between prompts when emitting for multiple skills.
_PROMPT_DELIMITER = "# === skillcheck:critique-prompt:{path} ==="

# Delimiter used between graph renders when emitting for multiple skills.
_GRAPH_DELIMITER = "# === skillcheck:graph:{path} ==="

# Delimiter used between graph-extraction prompts when emitting for multiple skills.
_GRAPH_PROMPT_DELIMITER = "# === skillcheck:graph-prompt:{path} ==="


# ---------------------------------------------------------------------------
# Path collection
# ---------------------------------------------------------------------------


def collect_paths(target: Path) -> list[Path]:
    """Return a list of SKILL.md files to validate.

    For a directory, recursively finds all files named exactly 'SKILL.md'.
    For a file, returns it directly without name filtering.
    """
    if target.is_dir():
        return sorted(target.rglob("SKILL.md"))
    return [target]


def resolve_paths(args: argparse.Namespace) -> list[Path]:
    """Resolve the target paths to a list of SKILL.md files, exiting on error."""
    all_paths: list[Path] = []
    for target in args.path:
        if not target.exists():
            print(f"Error: path not found: {target}", file=sys.stderr)
            sys.exit(2)
        paths = collect_paths(target)
        if not paths:
            print(f"No SKILL.md files found under: {target}", file=sys.stderr)
            sys.exit(2)
        all_paths.extend(paths)
    return all_paths


def read_ingest_raw(ingest_path: str) -> str:
    """Read the raw critique response from PATH or stdin, exiting on error.

    Rejects payloads over ``MAX_INGEST_BYTES`` (exit 2). The stdin read is
    bounded so a runaway pipe cannot exhaust memory before the check fires.
    """
    if ingest_path == "-":
        raw = sys.stdin.read(MAX_INGEST_BYTES + 1)
        size = len(raw.encode("utf-8"))
        if size > MAX_INGEST_BYTES:
            print(
                f"Error: ingest payload from stdin exceeds the {MAX_INGEST_BYTES}-byte cap. "
                f"Trim the response or split the run into smaller batches.",
                file=sys.stderr,
            )
            sys.exit(2)
        return raw
    p = Path(ingest_path)
    if not p.exists():
        print(f"Error: critique response file not found: {p}", file=sys.stderr)
        sys.exit(2)
    size = p.stat().st_size
    if size > MAX_INGEST_BYTES:
        print(
            f"Error: ingest response {p} is {size} bytes, over the {MAX_INGEST_BYTES}-byte cap. "
            f"Trim the response or split the run into smaller batches.",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"Error: cannot read {p}: {exc}", file=sys.stderr)
        sys.exit(2)


def _parse_or_exit(path: Path) -> ParsedSkill:
    """Parse a skill for an emit or history mode, or exit cleanly on failure.

    Plain validation renders an unparseable file (non-UTF-8, non-mapping
    frontmatter) as a clean ``parse.error`` diagnostic. The emit and history
    modes bypass that pipeline, so they mirror the behavior here: print the
    ParseError message to stderr and exit 1 instead of surfacing a traceback.
    """
    try:
        return _parse_skill(path)
    except ParseError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Emit modes
# ---------------------------------------------------------------------------


def emit_graph(paths: list[Path], fmt: str) -> None:
    """Print the capability graph for each path and exit 0."""
    multiple = len(paths) > 1
    for path in paths:
        skill = _parse_or_exit(path)
        graph = extract_graph_heuristic(skill)
        if multiple:
            print(_GRAPH_DELIMITER.format(path=path))
        if fmt == "json":
            print(render_graph_json(graph))
        else:
            print(render_graph_text(graph))


def emit_critique_prompts(paths: list[Path], fmt: str, agent_id: str = "claude") -> None:
    """Print critique prompts to stdout and exit 0."""
    multiple = len(paths) > 1
    for path in paths:
        skill = _parse_or_exit(path)
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


def emit_graph_prompts(paths: list[Path], fmt: str, agent_id: str = "claude") -> None:
    """Print graph-extraction prompts to stdout and exit 0."""
    multiple = len(paths) > 1
    for path in paths:
        skill = _parse_or_exit(path)
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


def emit_agent_reason_packet(paths: list[Path], fmt: str, critique_agent: str, graph_agent: str) -> None:
    """Print a combined critique and graph prompt packet for in-agent execution."""
    packets: list[dict[str, str]] = []
    for path in paths:
        skill = _parse_or_exit(path)
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


def emit_activation(paths: list[Path], fmt: str) -> None:
    """Print activation hypotheses for each path and exit 0."""
    multiple = len(paths) > 1
    reports = [generate_activation_hypotheses(_parse_or_exit(path)) for path in paths]
    if fmt == "json":
        if multiple:
            payload = [json.loads(render_activation_json(report)) for report in reports]
            print(json.dumps({"activation_reports": payload}, indent=2))
        else:
            print(render_activation_json(reports[0]))
        return

    for path, report in zip(paths, reports, strict=True):
        if multiple:
            print(f"# === skillcheck:activation:{path} ===")
        if fmt == "md":
            print(render_activation_markdown(report))
        else:
            print(render_activation_text(report))


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def run_show_history(args: argparse.Namespace, paths: list[Path]) -> None:
    """Print the validation history ledger for the first path and exit.

    Each skill has its own per-skill ledger, so multi-target invocations cannot
    map onto a single ledger render; the additional paths are ignored with a
    stderr warning so the silent skip is visible.
    """
    if len(paths) > 1:
        print(
            f"warning: --show-history reads one ledger; ignoring extra paths: "
            f"{', '.join(str(p) for p in paths[1:])}. "
            f"Run --show-history once per skill to read its ledger.",
            file=sys.stderr,
        )
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


# ---------------------------------------------------------------------------
# Default validation pipeline
# ---------------------------------------------------------------------------


def _compute_exit_code(
    results: list[ValidationResult],
    *,
    symbolic_errors_before_ingest: bool,
    any_ingest_failed: bool,
    strict_all: bool,
) -> int:
    """Return the process exit code from the merged results.

    Priority: symbolic/ingest failure (1) beats a semantic-only contradiction (3);
    a remaining error (e.g. an agent-graph contradiction) is 1; a warning-only run
    is 0 unless ``--strict`` escalates it to 1; otherwise 0.
    """
    if symbolic_errors_before_ingest or any_ingest_failed:
        return 1
    if any(
        d.severity == Severity.ERROR
        for r in results
        for d in r.diagnostics
        if d.rule.startswith("semantic.")
    ):
        # Symbolic passed, all parses succeeded, but a critique ingest added a
        # semantic-namespace contradiction (semantic.*).
        return 3
    if any(not r.valid for r in results):
        # Any remaining errors (e.g. graph.contradiction from agent ingest).
        return 1
    if any(d.severity == Severity.WARNING for r in results for d in r.diagnostics):
        # Warning-only runs are a clean pass by default; --strict escalates
        # them to exit 1. Exit 2 stays reserved for tool-misuse / input errors.
        return 1 if strict_all else 0
    return 0


def _record_history(
    args: argparse.Namespace,
    paths: list[Path],
    results: list[ValidationResult],
    agent_id: str,
    graph_agent_id: str,
    final_exit_code: int,
) -> int:
    """Append a ledger entry per target and merge any regression diagnostics.

    Mutates ``results`` in place (regression/write-failure diagnostics are
    appended per target). Each SKILL.md has its own per-skill ledger next to it.
    Returns the exit code, escalated to 1 the first time a target regresses when
    ``--fail-on-regression`` is set.
    """
    modes = ValidationModes(
        symbolic=True,
        critique=args.ingest_critique is not None,
        graph=args.ingest_graph is not None or args.analyze_graph,
    )
    run_agents = RunAgents(
        critique_agent=agent_id if args.ingest_critique is not None else None,
        graph_agent=graph_agent_id if args.ingest_graph is not None else None,
    )
    for index, path in enumerate(paths):
        skill_for_history = _parse_or_exit(path)
        preliminary_entry = build_entry(
            skill_for_history,
            results[index],
            modes,
            run_agents,
            final_exit_code,
            __version__,
        )
        lp = ledger_path_for(path)
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
            results[index] = merge_diagnostics(results[index], regression_diags)
            # Regression is WARNING by default; does not change the exit code.
            # --fail-on-regression promotes it to exit 1 the first time any
            # target regresses, and that escalated code is what subsequent
            # ledger entries (and the global exit) record.
            if args.fail_on_regression and any(
                d.rule == "history.skill.regressed" for d in regression_diags
            ):
                final_exit_code = 1

        # Build final entry with all diagnostics included (regression if any).
        final_entry = build_entry(
            skill_for_history,
            results[index],
            modes,
            run_agents,
            final_exit_code,
            __version__,
        )
        try:
            append_run(lp, skill_for_history, final_entry)
        except LedgerError as exc:
            results[index] = merge_diagnostics(results[index], [
                Diagnostic(
                    rule="history.write.failed",
                    severity=Severity.WARNING,
                    message=f"Could not write history ledger to {lp}: {exc}",
                )
            ])
            # Write failure is a warning; validation exit code stands.
    return final_exit_code


def _print_report(
    args: argparse.Namespace,
    results: list[ValidationResult],
    *,
    critique_source: str | None,
    graph_source_json: dict[str, Any] | None,
    graph_source_text: str | None,
) -> None:
    """Print the report in the requested format (no-op under --quiet)."""
    # Compute description quality score breakdowns when relevant.
    score_breakdowns: dict[str, dict[str, int]] = {}
    has_quality_diag = any(
        d.rule == "description.quality-score"
        for r in results
        for d in r.diagnostics
    )
    if has_quality_diag:
        from skillcheck.rules.description import score_description as _score
        from skillcheck.template_detection import is_template
        for r in results:
            for d in r.diagnostics:
                if d.rule == "description.quality-score":
                    try:
                        skill = _parse_skill(r.path)
                        desc = skill.frontmatter.get("description")
                        if desc and isinstance(desc, str) and desc.strip() and not is_template(skill):
                            _, _, bd = _score(desc)
                            score_breakdowns[str(r.path)] = bd
                    except Exception:
                        pass
                    break  # one description per file

    if args.quiet:
        return

    if args.format == "json":
        print(_format_json(
            results,
            __version__,
            critique_source=critique_source,
            graph_source=graph_source_json,
            score_breakdowns=score_breakdowns or None,
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
            score_breakdowns=score_breakdowns or None,
            explain_score=args.explain_score,
        ))


def run_validation(
    args: argparse.Namespace,
    paths: list[Path],
    agent_id: str,
    graph_agent_id: str,
) -> None:
    """Run symbolic validation, merge any ingested diagnostics, record history,
    print the report, and exit with the computed code."""
    # An ingested agent response describes exactly one skill, so it cannot be
    # fanned out across multiple resolved paths without stamping the first
    # skill's diagnostics onto every file. Reject the combination up front.
    if len(paths) > 1:
        active_ingest_flags = [
            flag
            for flag, value in (
                ("--ingest-critique", args.ingest_critique),
                ("--ingest-graph", args.ingest_graph),
            )
            if value is not None
        ]
        if active_ingest_flags:
            flags = " and ".join(active_ingest_flags)
            print(
                f"Error: {flags} applies one agent response to one skill, but "
                f"{len(paths)} SKILL.md paths were resolved. Run it once per skill, "
                f"pointing at a single SKILL.md.",
                file=sys.stderr,
            )
            sys.exit(2)

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
    graph_source_json: dict[str, Any] | None = None
    any_ingest_failed = False

    if args.ingest_critique is not None:
        raw = read_ingest_raw(args.ingest_critique)

        try:
            first_skill = _parse_or_exit(paths[0])
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

        results = [merge_diagnostics(r, critique_diags) for r in results]
        critique_source = agent_id

    if args.ingest_graph is not None:
        raw_graph = read_ingest_raw(args.ingest_graph)

        try:
            first_skill = _parse_or_exit(paths[0])
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
        for i, (path, result) in enumerate(zip(paths, results, strict=True)):
            skill = _parse_or_exit(path)
            graph = extract_graph_heuristic(skill)
            graph_diags = run_graph_analyzers(graph)
            results[i] = merge_diagnostics(result, graph_diags)
        graph_source_text = "heuristic"
        graph_source_json = {"mode": "heuristic"}

    # Determine exit code from current results (before history processing).
    final_exit_code = _compute_exit_code(
        results,
        symbolic_errors_before_ingest=symbolic_errors_before_ingest,
        any_ingest_failed=any_ingest_failed,
        strict_all=args.strict_all,
    )

    # --history runs before the final print so regression/write-fail diagnostics
    # appear in the report, and it may escalate the exit code.
    if args.history:
        final_exit_code = _record_history(
            args, paths, results, agent_id, graph_agent_id, final_exit_code
        )

    _print_report(
        args,
        results,
        critique_source=critique_source,
        graph_source_json=graph_source_json,
        graph_source_text=graph_source_text,
    )

    sys.exit(final_exit_code)
