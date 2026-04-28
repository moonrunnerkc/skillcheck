from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


def _source_for_rule(rule: str) -> str:
    if rule.startswith("frontmatter.name") or rule.startswith("frontmatter.description"):
        return "spec"
    if rule.startswith("sizing.") or rule.startswith("disclosure."):
        return "spec"
    if rule.startswith("compat.claude-only") or rule.startswith("compat.vscode-dirname"):
        return "spec"
    if rule.startswith("graph.contradiction.") or rule.startswith("semantic."):
        return "agent"
    if rule.startswith("graph."):
        return "heuristic"
    if rule.startswith("history."):
        return "history"
    return "advisory"


def _confidence_for_source(source: str) -> str:
    return {
        "spec": "high",
        "advisory": "medium",
        "heuristic": "medium",
        "agent": "low",
        "history": "high",
    }.get(source, "medium")


@dataclass(frozen=True)
class Diagnostic:
    rule: str
    severity: Severity
    message: str
    line: int | None = None
    context: str | None = None
    source: str | None = None
    confidence: str | None = None

    def __post_init__(self) -> None:
        source = self.source or _source_for_rule(self.rule)
        confidence = self.confidence or _confidence_for_source(source)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "confidence", confidence)


@dataclass(frozen=True)
class ValidationResult:
    path: Path
    diagnostics: list[Diagnostic]

    @property
    def valid(self) -> bool:
        return all(d.severity != Severity.ERROR for d in self.diagnostics)
