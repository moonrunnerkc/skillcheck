from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Diagnostic:
    rule: str
    severity: Severity
    message: str
    line: int | None = None
    context: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    path: Path
    diagnostics: list[Diagnostic]

    @property
    def valid(self) -> bool:
        return all(d.severity != Severity.ERROR for d in self.diagnostics)
