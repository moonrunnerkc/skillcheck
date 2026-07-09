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
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def _entry_from_dict(data: dict[str, Any], path: Path) -> LedgerEntry:
    """Deserialize a LedgerEntry from a dict. Raises LedgerError on missing keys."""
    try:
        modes_d = data["validation_modes"]
        agents_d = data["agents"]
        result_d = data["result"]
        return LedgerEntry(
            timestamp_utc=data["timestamp_utc"],
            skillcheck_version=data["skillcheck_version"],
            skill_content_hash=data["skill_content_hash"],
            validation_modes=ValidationModes(
                symbolic=modes_d["symbolic"],
                critique=modes_d["critique"],
                graph=modes_d["graph"],
            ),
            agents=RunAgents(
                critique_agent=agents_d["critique_agent"],
                graph_agent=agents_d["graph_agent"],
            ),
            result=ResultCounts(
                error=result_d["error"],
                warning=result_d["warning"],
                info=result_d["info"],
                valid=result_d["valid"],
            ),
            exit_code=data["exit_code"],
        )
    except KeyError as exc:
        raise LedgerError(
            f"Ledger at {path} is missing required field {exc}. "
            f"The file may be from a different schema version or is corrupt. "
            f"Delete it and re-run with --history to start fresh."
        ) from exc


def load_ledger(path: Path) -> Ledger | None:
    """Load and parse the ledger file at *path*.

    Args:
        path: Path to a ``.skillcheck-history.json`` file.

    Returns:
        Parsed Ledger, or None if the file does not exist.

    Raises:
        LedgerError: If the file exists but cannot be read or parsed.
    """
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LedgerError(
            f"Cannot read ledger at {path}: {exc}. "
            f"Check file permissions and retry."
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LedgerError(
            f"Ledger at {path} is not valid JSON: {exc}. "
            f"The file may be corrupt. Delete it and re-run with --history to start fresh."
        ) from exc

    if not isinstance(data, dict):
        raise LedgerError(
            f"Ledger at {path} must be a JSON object, got {type(data).__name__}. "
            f"The file is corrupt. Delete it and re-run with --history to start fresh."
        )

    try:
        version = data["version"]
        skill_path = data["skill_path"]
        runs_raw = data["runs"]
    except KeyError as exc:
        raise LedgerError(
            f"Ledger at {path} is missing top-level field {exc}. "
            f"The file may be incomplete or from an incompatible schema version."
        ) from exc

    if version != LEDGER_SCHEMA_VERSION:
        raise LedgerError(
            f"Ledger at {path} has schema version {version!r}, but this skillcheck "
            f"expects version {LEDGER_SCHEMA_VERSION}. Delete it and re-run with "
            f"--history to start fresh under the current schema."
        )

    if not isinstance(runs_raw, list):
        raise LedgerError(
            f"Ledger at {path} field 'runs' must be a list, got {type(runs_raw).__name__}. "
            f"The file is corrupt. Delete it and re-run with --history to start fresh."
        )

    try:
        runs = tuple(_entry_from_dict(r, path) for r in runs_raw)
    except TypeError as exc:
        raise LedgerError(
            f"Ledger at {path} contains a malformed run entry: {exc}. "
            f"The file is corrupt. Delete it and re-run with --history to start fresh."
        ) from exc
    return Ledger(version=version, skill_path=skill_path, runs=runs)


def save_ledger(path: Path, ledger: Ledger) -> None:
    """Serialize and write the ledger atomically via tempfile + rename.

    Writes to a temp file in the same directory as *path*, then uses
    ``os.replace`` (atomic on POSIX; best-effort on Windows). If the
    directory does not exist, the OS error propagates as LedgerError.

    Args:
        path: Destination path for the ledger file.
        ledger: Ledger to serialize.

    Raises:
        LedgerError: If the write or rename fails.
    """
    payload = {
        "version": ledger.version,
        "skill_path": ledger.skill_path,
        "runs": [_entry_to_dict(e) for e in ledger.runs],
    }
    serialized = json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False)

    try:
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".skillcheck-tmp-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(serialized)
                f.write("\n")
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError as exc:
        raise LedgerError(
            f"Cannot write ledger to {path}: {exc}. "
            f"Check directory permissions or disk space."
        ) from exc


def append_run(
    path: Path,
    skill: ParsedSkill,
    entry: LedgerEntry,
) -> Ledger:
    """Load or initialize the ledger, append the entry, save, and return the new ledger.

    On first call (no ledger file), initializes with ``version=LEDGER_SCHEMA_VERSION``
    and ``skill_path`` set to the relative path of the skill from the ledger directory.

    On subsequent calls, verifies that the existing ledger's ``skill_path`` matches
    before appending. A mismatch means the ledger file landed in the wrong place.

    Args:
        path: Path to the ``.skillcheck-history.json`` ledger file.
        skill: The skill that was validated (used to derive ``skill_path``).
        entry: The entry to append.

    Returns:
        The updated Ledger with the new entry appended.

    Raises:
        LedgerError: If the existing ledger is for a different skill, or if any
            I/O operation fails.
    """
    existing = load_ledger(path)

    try:
        relative_skill_path = str(skill.path.relative_to(path.parent))
    except ValueError:
        # Skill is not beneath the ledger directory (e.g., different drive on Windows).
        # Fall back to the absolute path as a string so the ledger is still useful.
        relative_skill_path = str(skill.path)

    if existing is None:
        ledger = Ledger(
            version=LEDGER_SCHEMA_VERSION,
            skill_path=relative_skill_path,
            runs=(entry,),
        )
    else:
        if existing.skill_path != relative_skill_path:
            raise LedgerError(
                f"Ledger at {path} is for skill '{existing.skill_path}' but the current skill "
                f"resolves to '{relative_skill_path}'. The ledger file may have been moved or "
                f"the skill was renamed. Delete the ledger and re-run with --history to restart."
            )
        ledger = Ledger(
            version=existing.version,
            skill_path=existing.skill_path,
            runs=existing.runs + (entry,),
        )

    save_ledger(path, ledger)
    return ledger


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
