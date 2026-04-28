"""Rich reasoning-trace reporter module for skillcheck v1.0."""

from __future__ import annotations

from skillcheck.result import Diagnostic, Severity, ValidationResult


def _sev_symbol(severity: Severity) -> str:
    return {Severity.ERROR: "✗", Severity.WARNING: "⚠", Severity.INFO: "·"}.get(severity, "·")


def _diagnostic_md_row(d: Diagnostic) -> str:
    loc = str(d.line) if d.line is not None else ""
    note = f"{d.message} ({d.context})" if d.context else d.message
    return f"| {loc} | {_sev_symbol(d.severity)} {d.severity.value} | `{d.rule}` | {note} |"


def render_markdown_report(result: ValidationResult) -> str:
    """Render a validation result into a markdown report.

    Args:
        result: Validation result to render.

    Returns:
        Markdown report as a string. Includes a pass/fail heading, a
        summary line, and a diagnostics table when issues are present.
    """
    status = "PASS" if result.valid else "FAIL"
    lines: list[str] = [
        f"## skillcheck report: {status}",
        "",
        f"**File:** `{result.path}`",
    ]

    errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
    warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
    infos = [d for d in result.diagnostics if d.severity == Severity.INFO]
    parts: list[str] = []
    if errors:
        parts.append(f"{len(errors)} error{'s' if len(errors) != 1 else ''}")
    if warnings:
        parts.append(f"{len(warnings)} warning{'s' if len(warnings) != 1 else ''}")
    if infos:
        parts.append(f"{len(infos)} info")
    summary = ", ".join(parts) if parts else "no issues"
    lines.append(f"**Result:** {summary}")

    if result.diagnostics:
        lines.append("")
        lines.append("| Line | Severity | Rule | Message |")
        lines.append("|------|----------|------|---------|")
        for d in result.diagnostics:
            lines.append(_diagnostic_md_row(d))

    return "\n".join(lines)


def render_json_report(result: ValidationResult) -> dict[str, object]:
    """Render a validation result into a structured JSON payload.

    Args:
        result: Validation result to render.

    Returns:
        JSON-serializable dict with keys: path, valid, error_count,
        warning_count, info_count, diagnostics.
    """
    errors = sum(1 for d in result.diagnostics if d.severity == Severity.ERROR)
    warnings = sum(1 for d in result.diagnostics if d.severity == Severity.WARNING)
    infos = sum(1 for d in result.diagnostics if d.severity == Severity.INFO)
    return {
        "path": str(result.path),
        "valid": result.valid,
        "error_count": errors,
        "warning_count": warnings,
        "info_count": infos,
        "diagnostics": [
            {
                "rule": d.rule,
                "severity": d.severity.value,
                "message": d.message,
                "line": d.line,
                "context": d.context,
            }
            for d in result.diagnostics
        ],
    }
