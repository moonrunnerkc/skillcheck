"""Validation history ledger for skillcheck.

Each SKILL.md that is validated with ``--history`` gets a companion
``.skillcheck-history.json`` file next to it. The ledger is append-only and
contains one ``LedgerEntry`` per run. It records validation quality over time:
which modes ran, which agents were used, and whether the skill was valid. It
does NOT record diagnostic messages, skill content, agent prompts, agent
responses, machine identifiers, or user identifiers. Safe to commit to git.

Schema versioning: the top-level ``version`` field starts at 1. Any breaking
change to the entry shape (added required field, removed field, type change)
must increment the version. The field order documented in the dataclasses
below is part of the contract; serialization preserves it via ordered dict
construction with ``sort_keys=False``.

Module dependency rule: imports only from stdlib plus ``parser`` and ``result``
sibling modules. No ``agents`` imports. No ``cli`` imports.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity, ValidationResult

# ---------------------------------------------------------------------------
# Schema version (increment on breaking changes only)
# ---------------------------------------------------------------------------

LEDGER_SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class LedgerError(Exception):
    """Raised on ledger I/O or structural failures.

    Always raised with ``raise LedgerError(...) from original_exc`` so the
    original cause is preserved for debugging.
    """


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResultCounts:
    """Diagnostic count summary for one validation run."""

    error: int
    warning: int
    info: int
    valid: bool

    def __str__(self) -> str:
        return f"error={self.error} warning={self.warning} info={self.info} valid={self.valid}"


@dataclass(frozen=True, slots=True)
class ValidationModes:
    """Which validation modes contributed diagnostics to a run."""

    symbolic: bool
    critique: bool
    graph: bool


@dataclass(frozen=True, slots=True)
class RunAgents:
    """Which agents were used during a run. None when a mode did not run or used heuristics."""

    critique_agent: str | None
    graph_agent: str | None


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One recorded validation run.

    All fields are required. Field order here is the serialization order.
    """

    timestamp_utc: str         # ISO 8601 second-precision, Z suffix: 2026-04-24T15:30:00Z
    skillcheck_version: str    # From __version__
    skill_content_hash: str    # SHA-256 of raw_text, first 16 hex chars
    validation_modes: ValidationModes
    agents: RunAgents
    result: ResultCounts
    exit_code: int


@dataclass(frozen=True, slots=True)
class Ledger:
    """Complete ledger for one skill file."""

    version: int                      # LEDGER_SCHEMA_VERSION
    skill_path: str                   # Relative path of skill from ledger directory
    runs: tuple[LedgerEntry, ...]


# ---------------------------------------------------------------------------
# Pure / deterministic functions
# ---------------------------------------------------------------------------


def compute_skill_hash(skill: ParsedSkill) -> str:
    """Return the first 16 hex chars of the SHA-256 hash of the skill's raw text.

    Deterministic across runs of the same file content. Detects whether the
    skill itself changed between two ledger entries.

    The 64-bit truncation is intentional: ledger size matters more than
    cryptographic collision resistance, and the regression check compares
    hashes only within one skill's own ledger.  The per-pair false-match
    probability is about 1e-19, which is acceptable for that use.  Do not
    use this hash for any cross-skill or security-sensitive purpose.

    Args:
        skill: Parsed skill file.

    Returns:
        16-character lowercase hex string.
    """
    digest = hashlib.sha256(skill.raw_text.encode("utf-8", errors="replace")).hexdigest()
    return digest[:16]


def build_entry(
    skill: ParsedSkill,
    result: ValidationResult,
    modes: ValidationModes,
    agents: RunAgents,
    exit_code: int,
    version: str,
    now: datetime | None = None,
) -> LedgerEntry:
    """Construct a LedgerEntry without performing any I/O.

    Args:
        skill: Parsed skill, used for the content hash.
        result: Final validation result (after all merges).
        modes: Which validation modes contributed diagnostics.
        agents: Which agents were used.
        exit_code: The exit code that will be returned.
        version: The skillcheck version string (from ``__version__``).
        now: Injectable datetime for testing. Defaults to ``datetime.now(timezone.utc)``.

    Returns:
        A fully-populated, frozen LedgerEntry.
    """
    ts = (now if now is not None else datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

    error_count = sum(1 for d in result.diagnostics if d.severity == Severity.ERROR)
    warning_count = sum(1 for d in result.diagnostics if d.severity == Severity.WARNING)
    info_count = sum(1 for d in result.diagnostics if d.severity == Severity.INFO)

    return LedgerEntry(
        timestamp_utc=ts,
        skillcheck_version=version,
        skill_content_hash=compute_skill_hash(skill),
        validation_modes=modes,
        agents=agents,
        result=ResultCounts(
            error=error_count,
            warning=warning_count,
            info=info_count,
            valid=result.valid,
        ),
        exit_code=exit_code,
    )


def ledger_path_for(skill_path: Path) -> Path:
    """Return the ledger file path for a given skill path.

    The ledger lives next to the skill file, named ``.skillcheck-history.json``.

    Args:
        skill_path: Absolute or relative path to the SKILL.md file.

    Returns:
        Path to ``.skillcheck-history.json`` in the same directory.
    """
    return skill_path.parent / ".skillcheck-history.json"


def check_regression(
    prior_runs: tuple[LedgerEntry, ...],
    current_entry: LedgerEntry,
) -> list[Diagnostic]:
    """Return a regression diagnostic if a passing run now fails on the same content.

    Algorithm: find any prior entry whose ``skill_content_hash`` matches the
    current entry AND whose ``result.valid`` is True. If the current run
    failed (``result.valid`` is False), emit one WARNING. Uses the most
    recent matching prior run for the timestamp reference.

    Args:
        prior_runs: All runs recorded before this one.
        current_entry: The entry that is about to be appended.

    Returns:
        A list with at most one ``history.skill.regressed`` WARNING diagnostic.
    """
    if current_entry.result.valid:
        return []

    matching = [
        r for r in prior_runs
        if r.skill_content_hash == current_entry.skill_content_hash and r.result.valid
    ]
    if not matching:
        return []

    # Most recent matching prior (last in append order).
    prior = matching[-1]
    return [
        Diagnostic(
            rule="history.skill.regressed",
            severity=Severity.WARNING,
            message=(
                f"Skill content unchanged since {prior.timestamp_utc} when validation passed, "
                f"but is now failing. Either a skillcheck rule has tightened or an agent "
                f"surfaced a new finding. Compare diagnostic counts: "
                f"prior {prior.result}, current {current_entry.result}."
            ),
        )
    ]


# ---------------------------------------------------------------------------
# I/O functions
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Serialization (shared by the JSON renderer and the I/O module)
# ---------------------------------------------------------------------------


def _entry_to_dict(entry: LedgerEntry) -> dict[str, object]:
    """Serialize a LedgerEntry to an ordered dict. Field order matches dataclass."""
    return {
        "timestamp_utc": entry.timestamp_utc,
        "skillcheck_version": entry.skillcheck_version,
        "skill_content_hash": entry.skill_content_hash,
        "validation_modes": {
            "symbolic": entry.validation_modes.symbolic,
            "critique": entry.validation_modes.critique,
            "graph": entry.validation_modes.graph,
        },
        "agents": {
            "critique_agent": entry.agents.critique_agent,
            "graph_agent": entry.agents.graph_agent,
        },
        "result": {
            "error": entry.result.error,
            "warning": entry.result.warning,
            "info": entry.result.info,
            "valid": entry.result.valid,
        },
        "exit_code": entry.exit_code,
    }


# ---------------------------------------------------------------------------
# Text renderer for --show-history
# ---------------------------------------------------------------------------


def render_ledger_text(ledger: Ledger) -> str:
    """Render a ledger as human-readable text for --show-history --format text.

    Args:
        ledger: Ledger to render.

    Returns:
        Multi-line string. Each run is one block.
    """
    lines: list[str] = [
        f"History ledger: {ledger.skill_path}",
        f"Schema version: {ledger.version}",
        f"Total runs: {len(ledger.runs)}",
        "",
    ]
    for i, run in enumerate(ledger.runs, start=1):
        validity = "PASS" if run.result.valid else "FAIL"
        modes = []
        if run.validation_modes.symbolic:
            modes.append("symbolic")
        if run.validation_modes.critique:
            agent_label = (
                f"critique({run.agents.critique_agent})"
                if run.agents.critique_agent
                else "critique"
            )
            modes.append(agent_label)
        if run.validation_modes.graph:
            agent_label = (
                f"graph({run.agents.graph_agent})"
                if run.agents.graph_agent
                else "graph(heuristic)"
            )
            modes.append(agent_label)
        mode_str = ", ".join(modes) if modes else "none"
        lines.append(f"Run {i:>3}  {run.timestamp_utc}  {validity}  exit={run.exit_code}")
        lines.append(f"         version={run.skillcheck_version}  hash={run.skill_content_hash}")
        lines.append(f"         modes=[{mode_str}]")
        lines.append(
            f"         errors={run.result.error} warnings={run.result.warning} info={run.result.info}"
        )
        lines.append("")
    return "\n".join(lines).rstrip()


def render_ledger_json(ledger: Ledger) -> str:
    """Render a ledger as JSON for --show-history --format json.

    Args:
        ledger: Ledger to render.

    Returns:
        JSON string (indented, deterministic field order).
    """
    payload = {
        "version": ledger.version,
        "skill_path": ledger.skill_path,
        "runs": [_entry_to_dict(e) for e in ledger.runs],
    }
    return json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False)


# Ledger filesystem I/O lives in history_io.py (which imports the model and the
# serializer above). Re-exported here so the historical public surface
# ``from skillcheck.core.history import load_ledger`` keeps working. The import
# sits at the bottom because history_io depends on this module's definitions.
from skillcheck.core.history_io import (  # noqa: E402
    append_run,
    load_ledger,
    save_ledger,
)

__all__ = [
    "LEDGER_SCHEMA_VERSION",
    "Ledger",
    "LedgerEntry",
    "LedgerError",
    "ResultCounts",
    "RunAgents",
    "ValidationModes",
    "append_run",
    "build_entry",
    "check_regression",
    "compute_skill_hash",
    "ledger_path_for",
    "load_ledger",
    "render_ledger_json",
    "render_ledger_text",
    "save_ledger",
]
