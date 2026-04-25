"""Validation history ledger module for skillcheck v1.0."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


HISTORY_STUB_MESSAGE = "Validation history ledger lands in v1.0."


@dataclass(frozen=True)
class ValidationSnapshot:
    """One persisted validation event for historical analysis."""

    timestamp: str
    path: str
    valid: bool
    metadata: dict[str, Any]


def append_validation_snapshot(history_path: Path, snapshot: ValidationSnapshot) -> None:
    """Append one validation snapshot to the history ledger.

    Args:
        history_path: Path to the history ledger file.
        snapshot: Validation event to append.

    Raises:
        NotImplementedError: Always raised in Phase 0 scaffolding.
    """
    raise NotImplementedError(HISTORY_STUB_MESSAGE)
