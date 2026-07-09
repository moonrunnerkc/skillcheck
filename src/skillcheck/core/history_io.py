"""Filesystem I/O for the validation history ledger.

Serialization, atomic writes, and load/append of ``.skillcheck-history.json``
live here, separated from the model, regression, and rendering logic in
``history.py``. ``history.py`` re-exports ``load_ledger``, ``save_ledger``, and
``append_run`` so ``from skillcheck.core.history import load_ledger`` still works.

Concurrency: single-writer. A ledger sits next to its SKILL.md and is written by
one ``skillcheck ... --history`` process at a time (typically a pre-commit hook
or a CI step). There is no file locking; two processes writing the same ledger
concurrently is unsupported and can lose the interleaved run. Writes are atomic
per process (temp file, ``flush`` + ``fsync``, then ``os.replace``), and stale
temp files from an interrupted write are swept on the next load.

Module dependency rule: imports only from stdlib plus the ``history`` model and
the ``parser`` sibling module. No ``agents`` imports. No ``cli`` imports.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from skillcheck.core.history import (
    LEDGER_SCHEMA_VERSION,
    Ledger,
    LedgerEntry,
    LedgerError,
    ResultCounts,
    RunAgents,
    ValidationModes,
    _entry_to_dict,
)
from skillcheck.parser import ParsedSkill


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


def _sweep_stale_tmp_files(directory: Path) -> None:
    """Remove leftover ``.skillcheck-tmp-*`` files from an interrupted write.

    ``save_ledger`` writes to a temp file and renames it into place; if the
    process is killed between ``mkstemp`` and ``os.replace``, the temp file is
    orphaned. Under the single-writer assumption these are always stale, so they
    are removed on the next load. Errors (permissions, races) are ignored.
    """
    try:
        stale = directory.glob(".skillcheck-tmp-*")
    except OSError:
        return
    for tmp in stale:
        try:
            tmp.unlink()
        except OSError:
            pass


def load_ledger(path: Path) -> Ledger | None:
    """Load and parse the ledger file at *path*.

    Args:
        path: Path to a ``.skillcheck-history.json`` file.

    Returns:
        Parsed Ledger, or None if the file does not exist.

    Raises:
        LedgerError: If the file exists but cannot be read or parsed.
    """
    _sweep_stale_tmp_files(path.parent)
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
                # Force the bytes to disk before the rename so a crash between
                # replace and the OS flushing its cache cannot leave a truncated
                # ledger. The temp fd is fsynced while still open.
                f.flush()
                os.fsync(f.fileno())
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
