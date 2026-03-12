#!/usr/bin/env python3
"""GitHub Action entrypoint for skillcheck.

Runs skillcheck with JSON output, emits PR annotations via workflow
commands, writes a job summary to $GITHUB_STEP_SUMMARY, and exits with
skillcheck's exit code.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


# ---------------------------------------------------------------------------
# Command builder
# ---------------------------------------------------------------------------


def _build_command() -> list[str]:
    """Build the skillcheck CLI invocation from INPUT_* env vars."""
    path = os.environ.get("INPUT_PATH", ".")
    cmd = ["skillcheck", path, "--format", "json", "--no-color"]

    if os.environ.get("INPUT_STRICT_VSCODE", "false") == "true":
        cmd.append("--strict-vscode")
    if os.environ.get("INPUT_SKIP_DIRNAME_CHECK", "false") == "true":
        cmd.append("--skip-dirname-check")
    if os.environ.get("INPUT_SKIP_REF_CHECK", "false") == "true":
        cmd.append("--skip-ref-check")

    min_score = os.environ.get("INPUT_MIN_DESC_SCORE", "")
    if min_score:
        cmd.extend(["--min-desc-score", min_score])

    agent = os.environ.get("INPUT_TARGET_AGENT", "")
    if agent:
        cmd.extend(["--target-agent", agent])

    ignore = os.environ.get("INPUT_IGNORE", "")
    if ignore:
        for prefix in ignore.split(","):
            stripped = prefix.strip()
            if stripped:
                cmd.extend(["--ignore", stripped])

    max_lines = os.environ.get("INPUT_MAX_LINES", "")
    if max_lines:
        cmd.extend(["--max-lines", max_lines])

    max_tokens = os.environ.get("INPUT_MAX_TOKENS", "")
    if max_tokens:
        cmd.extend(["--max-tokens", max_tokens])

    return cmd


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------

_SEVERITY_MAP = {"error": "error", "warning": "warning", "info": "notice"}


def _emit_annotations(data: dict) -> None:
    """Emit GitHub workflow commands so diagnostics appear inline on PRs."""
    for file_result in data.get("results", []):
        filepath = file_result["path"]
        for diag in file_result.get("diagnostics", []):
            severity = diag["severity"]
            line = diag.get("line")
            rule = diag["rule"]
            message = diag["message"]

            gh_level = _SEVERITY_MAP.get(severity, "notice")

            parts = [f"file={filepath}"]
            if line:
                parts.append(f"line={line}")
            loc = ",".join(parts)

            # Escape for workflow command protocol
            safe_msg = (
                message.replace("%", "%25")
                .replace("\r", "%0D")
                .replace("\n", "%0A")
            )
            print(f"::{gh_level} {loc},title=skillcheck: {rule}::{safe_msg}")


# ---------------------------------------------------------------------------
# Step summary
# ---------------------------------------------------------------------------


def _write_summary(data: dict) -> None:
    """Write a Markdown job summary to $GITHUB_STEP_SUMMARY."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    total = data["files_checked"]
    passed = data["files_passed"]
    failed = data["files_failed"]

    lines: list[str] = []

    if failed == 0:
        lines.append(f"### ✅ skillcheck — {passed}/{total} files passed\n")
    else:
        lines.append(f"### ❌ skillcheck — {failed}/{total} files failed\n")

    lines.append("| File | Status | Errors | Warnings |")
    lines.append("|------|--------|--------|----------|")

    for r in data.get("results", []):
        status = "✅" if r["valid"] else "❌"
        errors = sum(
            1 for d in r["diagnostics"] if d["severity"] == "error"
        )
        warnings = sum(
            1 for d in r["diagnostics"] if d["severity"] == "warning"
        )
        lines.append(f"| `{r['path']}` | {status} | {errors} | {warnings} |")

    # Expandable failure details
    failures = [r for r in data["results"] if not r["valid"]]
    if failures:
        lines.append("")
        lines.append("<details><summary>Failure details</summary>\n")
        for r in failures:
            lines.append(f"**{r['path']}**\n")
            for d in r["diagnostics"]:
                icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(
                    d["severity"], ""
                )
                loc = f"L{d['line']}" if d.get("line") else ""
                lines.append(
                    f"- {icon} {loc} `{d['rule']}` — {d['message']}"
                )
            lines.append("")
        lines.append("</details>")

    with open(summary_path, "a") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Log output
# ---------------------------------------------------------------------------

_SEV_SYMBOL = {"error": "✗", "warning": "⚠", "info": "·"}


def _print_log(data: dict) -> None:
    """Print a human-readable summary to stdout for the workflow log."""
    for r in data.get("results", []):
        tag = "PASS" if r["valid"] else "FAIL"
        icon = "✔" if r["valid"] else "✗"
        print(f"{icon} {tag}  {r['path']}")
        for d in r["diagnostics"]:
            sym = _SEV_SYMBOL.get(d["severity"], "·")
            loc = f"line {d['line']}" if d.get("line") else ""
            print(
                f"  {loc:>8}  {sym} {d['severity']:<7}  "
                f"{d['rule']}  {d['message']}"
            )

    total = data["files_checked"]
    passed = data["files_passed"]
    failed = data["files_failed"]
    noun = "file" if total == 1 else "files"
    print(f"\nChecked {total} {noun}: {passed} passed, {failed} failed")


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


def _set_outputs(data: dict, exit_code: int) -> None:
    """Write action outputs to $GITHUB_OUTPUT."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return

    with open(output_path, "a") as f:
        f.write(f"exit-code={exit_code}\n")
        f.write("json<<SKILLCHECK_JSON_EOF\n")
        f.write(json.dumps(data, indent=2))
        f.write("\nSKILLCHECK_JSON_EOF\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    cmd = _build_command()
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Input errors (exit 2) — no JSON to parse
    if result.returncode == 2:
        msg = result.stderr.strip() or "unknown input error"
        print(f"::error::skillcheck: {msg}")
        sys.exit(2)

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        print("::error::skillcheck produced unexpected output")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(2)

    _emit_annotations(data)
    _print_log(data)
    _write_summary(data)
    _set_outputs(data, result.returncode)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
