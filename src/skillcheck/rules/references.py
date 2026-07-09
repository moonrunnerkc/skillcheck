"""File reference validation for SKILL.md.

Checks that relative file references in the body actually exist on disk
and that reference depth stays within one level of the SKILL.md location,
per the agentskills.io spec recommendation.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from skillcheck.core.graph import extract_backtick_refs
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

# Matches HTML anchor tags: <a href="path">text</a>.  Excludes URL schemes
# the same way _MD_LINK_RE does.  href= may be single- or double-quoted.
_HTML_LINK_RE = re.compile(
    r"""<a\s+[^>]*?href\s*=\s*['"](?!https?://|mailto:)([^'"#\s]+)(?:#[^'"]*)?['"]""",
    re.IGNORECASE,
)

# Matches fenced code blocks, stripped before backtick-reference scanning so
# code samples that mention paths do not get flagged.  The regex matches both
# bare ``` and ```language fences; DOTALL allows the body to span newlines.
_FENCED_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)

# A backtick span looks like a *reference* only when it contains a directory
# separator: `scripts/foo.py` is clearly a file path, but `report.json`
# (without a directory) is more likely a generated output the SKILL.md
# names rather than a file that must already exist.  The graph extractor
# at core/graph.py harvests both shapes for capability inputs and outputs;
# the references rule keeps to the stricter shape to avoid flagging output
# mentions as broken file links.


def _extract_references(body: str) -> list[str]:
    """Extract all file reference paths from the markdown body."""
    refs: list[str] = []
    refs.extend(_MD_LINK_RE.findall(body))
    refs.extend(_DIRECTIVE_RE.findall(body))
    refs.extend(_HTML_LINK_RE.findall(body))
    code_free_body = _FENCED_CODE_BLOCK_RE.sub("", body)
    for candidate in extract_backtick_refs(code_free_body):
        candidate = candidate.strip()
        if not candidate or candidate.startswith(("http://", "https://", "mailto:")):
            continue
        # Reject content that is not a single path token: multi-line code-block
        # bodies (contain '\n'), command snippets (spaces), and template
        # placeholders (<path>, <name>, etc.).
        if any(ch in candidate for ch in " \n<>"):
            continue
        # A backtick span often holds an identifier, command, or option; only
        # treat it as a reference when it contains a directory separator.
        if "/" in candidate:
            refs.append(candidate)
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
    """Check that all file references in the body resolve to existing files.

    Also rejects symlinks (or ``..`` chains) that escape the skill directory
    tree.  Allowing unchecked symlinks would let a SKILL.md reference
    ``/etc/passwd`` via a crafted symlink (CWE-59 / path-traversal).
    """
    refs = _extract_references(skill.body)
    if not refs:
        return []

    skill_dir = skill.path.parent.resolve()
    diagnostics: list[Diagnostic] = []

    for ref in refs:
        target = (skill_dir / ref).resolve()

        # Containment check: the resolved target must stay inside the
        # skill directory tree.  This catches symlinks pointing outside,
        # as well as ``../../`` traversal that escapes the root.
        if not target.is_relative_to(skill_dir):
            diagnostics.append(Diagnostic(
                rule="references.escape",
                severity=Severity.ERROR,
                message=(
                    f"Reference '{ref}' resolves outside the skill directory. "
                    f"File references must stay within the skill tree."
                ),
                context=f"resolved to: {_relative_to_skill_dir(target, skill_dir)}",
            ))
            continue

        if not target.exists():
            diagnostics.append(Diagnostic(
                rule="references.broken-link",
                severity=Severity.ERROR,
                message=f"Referenced file does not exist: '{ref}'.",
                context=f"resolved to: {_relative_to_skill_dir(target, skill_dir)}",
            ))

    return diagnostics


def _relative_to_skill_dir(target: Path, skill_dir: Path) -> str:
    """Render *target* relative to *skill_dir* so diagnostics never leak the host path.

    A contained reference shows as ``scripts/foo.py``; an escaping one shows the
    traversal (``../../etc/passwd``). Either way the skill's absolute location on
    the build machine stays out of CI logs.
    """
    try:
        return target.relative_to(skill_dir).as_posix()
    except ValueError:
        return Path(os.path.relpath(target, skill_dir)).as_posix()


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
        elif ref.startswith(".."):
            diagnostics.append(Diagnostic(
                rule="references.depth-exceeded",
                severity=Severity.WARNING,
                message=(
                    f"Reference '{ref}' traverses above the skill directory. "
                    f"Use relative paths from the skill root."
                ),
            ))

    return diagnostics
