"""File reference validation for SKILL.md.

Checks that relative file references in the body actually exist on disk
and that reference depth stays within one level of the SKILL.md location,
per the agentskills.io spec recommendation.
"""

from __future__ import annotations

import re
from pathlib import Path

from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity

# Matches markdown links: [text](path) and ![alt](path)
# Captures the path portion. Excludes URLs (http://, https://, mailto:).
_MD_LINK_RE = re.compile(
    r"!?\[[^\]]*\]\((?!https?://|mailto:)([^)\s#]+)(?:#[^)]*)?\)"
)

# Matches bare file paths in the body that look like relative references.
# Covers patterns like `source: path/to/file` or `file: path/to/file`.
_DIRECTIVE_RE = re.compile(
    r"(?:source|file|include):\s*([^\s]+\.[a-zA-Z0-9]+)",
    re.IGNORECASE,
)


def _extract_references(body: str) -> list[str]:
    """Extract all file reference paths from the markdown body."""
    refs: list[str] = []
    refs.extend(_MD_LINK_RE.findall(body))
    refs.extend(_DIRECTIVE_RE.findall(body))
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            unique.append(ref)
    return unique


def _reference_depth(ref_path: str) -> int:
    """Count how many directory levels deep a reference goes from SKILL.md.

    A reference like "file.txt" is depth 0 (same directory).
    A reference like "sub/file.txt" is depth 1.
    A reference like "sub/deep/file.txt" is depth 2.
    A reference like "../other/file.txt" counts the '..' as traversal.
    """
    parts = Path(ref_path).parts
    # Filter out the filename itself
    dir_parts = parts[:-1] if len(parts) > 1 else ()
    return len(dir_parts)


def check_broken_references(skill: ParsedSkill) -> list[Diagnostic]:
    """Check that all file references in the body resolve to existing files."""
    refs = _extract_references(skill.body)
    if not refs:
        return []

    skill_dir = skill.path.parent
    diagnostics: list[Diagnostic] = []

    for ref in refs:
        target = (skill_dir / ref).resolve()
        if not target.exists():
            diagnostics.append(Diagnostic(
                rule="references.broken-link",
                severity=Severity.ERROR,
                message=f"Referenced file does not exist: '{ref}'.",
                context=f"resolved to: {target}",
            ))

    return diagnostics


def check_reference_depth(skill: ParsedSkill) -> list[Diagnostic]:
    """Warn when file references go deeper than one level from SKILL.md."""
    refs = _extract_references(skill.body)
    if not refs:
        return []

    diagnostics: list[Diagnostic] = []
    for ref in refs:
        depth = _reference_depth(ref)
        if depth > 1:
            diagnostics.append(Diagnostic(
                rule="references.depth-exceeded",
                severity=Severity.WARNING,
                message=(
                    f"Reference '{ref}' is {depth} levels deep. "
                    f"Keep file references one level deep from SKILL.md."
                ),
            ))
        # Also flag parent traversal
        if ref.startswith(".."):
            diagnostics.append(Diagnostic(
                rule="references.depth-exceeded",
                severity=Severity.WARNING,
                message=(
                    f"Reference '{ref}' traverses above the skill directory. "
                    f"Use relative paths from the skill root."
                ),
            ))

    return diagnostics
