from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skillcheck import __version__
from skillcheck.core import (
    ingest_critique_response,
    merge_critique_diagnostics,
    render_critique_prompt,
    validate,
)
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


def _format_text(results: list[ValidationResult], *, color: bool = False) -> str:
    lines: list[str] = []
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


def _format_json(results: list[ValidationResult], version: str) -> str:
    passed = sum(1 for r in results if r.valid)
    payload = {
        "version": version,
        "files_checked": len(results),
        "files_passed": passed,
        "files_failed": len(results) - passed,
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


def _do_emit_critique_prompts(paths: list[Path], fmt: str) -> None:
    """Print critique prompts to stdout and exit 0."""
    multiple = len(paths) > 1
    for path in paths:
        skill = _parse_skill(path)
        prompt = render_critique_prompt(skill)
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


def main() -> None:
    # Ensure UTF-8 output on Windows where the default encoding may be cp1252.
    if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    if sys.stderr.encoding and sys.stderr.encoding.lower().replace("-", "") != "utf8":
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    parser = _build_parser()
    args = parser.parse_args()

    # Mutual exclusion
    if args.emit_critique_prompt and args.ingest_critique is not None:
        print(
            "Cannot use --emit-critique-prompt and --ingest-critique together. "
            "Pick one: emit a prompt for your agent to execute, or ingest the agent's response.",
            file=sys.stderr,
        )
        sys.exit(2)

    paths = _resolve_paths(args)

    # --emit-critique-prompt: skip symbolic validation entirely
    if args.emit_critique_prompt:
        _do_emit_critique_prompts(paths, fmt=args.format)
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

    if args.ingest_critique is not None:
        raw = _read_ingest_raw(args.ingest_critique)
        symbolic_any_errors = any(not r.valid for r in results)
        ingest_failed = False

        try:
            # Use the first path for section-header line lookups; same critique
            # response applies across all results when multiple paths are given.
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
            ingest_failed = True

        results = [merge_critique_diagnostics(r, critique_diags) for r in results]
        semantic_any_errors = any(not r.valid for r in results)

        if not args.quiet:
            if args.format == "json":
                print(_format_json(results, __version__))
            else:
                use_color = not args.no_color and sys.stdout.isatty()
                print(_format_text(results, color=use_color))

        if ingest_failed or symbolic_any_errors:
            sys.exit(1)
        if semantic_any_errors:
            sys.exit(3)
        sys.exit(0)

    # Normal v0.2.0 path
    if not args.quiet:
        if args.format == "json":
            print(_format_json(results, __version__))
        else:
            use_color = not args.no_color and sys.stdout.isatty()
            print(_format_text(results, color=use_color))

    sys.exit(1 if any(not r.valid for r in results) else 0)
