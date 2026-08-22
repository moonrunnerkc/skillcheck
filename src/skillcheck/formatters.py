"""Output formatters for the skillcheck CLI.

Pure functions that convert ValidationResult lists into the user-facing
representations (text, JSON, markdown, agent, GitHub Actions commands).
No I/O. The CLI module owns argument parsing and orchestration; this
module owns presentation.
"""
from __future__ import annotations

import json

from skillcheck.config import DESCRIPTION_SCORE_WEIGHTS
from skillcheck.result import Severity, ValidationResult

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


def _format_text(
    results: list[ValidationResult],
    *,
    color: bool = False,
    critique_source: str | None = None,
    graph_source: str | None = None,
    score_breakdowns: dict[str, dict[str, int]] | None = None,
    explain_score: bool = False,
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
            # Explain description quality scores when requested
            if (
                explain_score
                and d.rule == "description.quality-score"
                and score_breakdowns
            ):
                bd = score_breakdowns.get(str(result.path))
                if bd:
                    parts = [
                        f"{name}: {bd.get(name, 0)}/{max_pts}"
                        for name, max_pts in DESCRIPTION_SCORE_WEIGHTS.items()
                    ]
                    lines.append(f"{'':>12}{' · '.join(parts)}")

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
    graph_source: dict[str, object] | None = None,
    score_breakdowns: dict[str, dict[str, int]] | None = None,
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
                        **{
                            "rule": d.rule,
                            "severity": d.severity.value,
                            "message": d.message,
                            "line": d.line,
                            "context": d.context,
                            "source": d.source,
                            "confidence": d.confidence,
                        },
                        **(
                            {"breakdown": score_breakdowns[str(r.path)]}
                            if d.rule == "description.quality-score"
                            and score_breakdowns
                            and str(r.path) in score_breakdowns
                            else {}
                        ),
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


def _escape_data(value: str) -> str:
    """Escape a GitHub Actions workflow-command message (the text after ``::``).

    Per the Actions toolkit, message data escapes only ``%``, CR, and LF. Colons
    and commas are literal here, so a diagnostic message like ``got 82): 'name'``
    renders as written instead of showing ``%3A``.
    """
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    """Escape a GitHub Actions workflow-command property value (``file``, ``title``).

    Property values additionally escape ``:`` and ``,`` because a comma separates
    properties and a colon ends the property section. GitHub decodes them for
    display, so the annotation still reads normally.
    """
    return _escape_data(value).replace(":", "%3A").replace(",", "%2C")


def _format_github(results: list[ValidationResult]) -> str:
    """Format diagnostics as GitHub Actions workflow commands for PR annotations."""
    severity_map = {
        Severity.ERROR: "error",
        Severity.WARNING: "warning",
        Severity.INFO: "notice",
    }
    lines: list[str] = []
    for result in results:
        filepath = _escape_property(str(result.path).replace("\\", "/"))
        for d in result.diagnostics:
            gh_level = severity_map.get(d.severity, "notice")
            parts = [f"file={filepath}"]
            if d.line is not None:
                parts.append(f"line={d.line}")
            parts.append(f"title={_escape_property(f'skillcheck: {d.rule}')}")
            props = ",".join(parts)
            message = _escape_data(d.message)
            lines.append(f"::{gh_level} {props}::{message}")
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


__all__ = [
    "_format_text",
    "_format_json",
    "_format_markdown",
    "_format_github",
    "_format_agent",
    "_escape_data",
    "_escape_property",
    "_style",
]
