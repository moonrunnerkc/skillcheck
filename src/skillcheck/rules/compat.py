"""Cross-agent compatibility warnings for SKILL.md.

The agentskills.io spec is consumed by Claude Code, VS Code/Copilot,
OpenAI Codex, Cursor, and other agents. Implementation-specific fields
work in one agent but are ignored or cause breakage in others.

This module flags fields with limited cross-agent support so authors
can make informed decisions about portability.
"""

from __future__ import annotations

from collections.abc import Callable

from skillcheck import config
from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity


def check_claude_only_fields(skill: ParsedSkill) -> list[Diagnostic]:
    """Flag fields that only work in Claude Code."""
    diagnostics: list[Diagnostic] = []
    for field in skill.frontmatter:
        if field in config.CLAUDE_ONLY_FIELDS:
            diagnostics.append(Diagnostic(
                rule="compat.claude-only",
                severity=Severity.INFO,
                message=(
                    f"Field '{field}' is Claude Code-specific. "
                    f"It will be ignored by VS Code/Copilot and behavior in "
                    f"Codex and Cursor is unverified."
                ),
            ))
    return diagnostics


def check_vscode_dirname(skill: ParsedSkill) -> list[Diagnostic]:
    """Info-level note when name does not match the parent directory.

    This complements the ERROR-level check in frontmatter.py (which can be
    skipped via --skip-dirname-check). This compat rule always runs as INFO
    unless --strict-vscode promotes it.
    """
    name = skill.frontmatter.get("name")
    if name is None:
        return []
    name = str(name)
    if not name:
        return []
    parent_dir = skill.path.parent.name
    if parent_dir and parent_dir != name:
        return [Diagnostic(
            rule="compat.vscode-dirname",
            severity=Severity.INFO,
            message=(
                f"VS Code requires the name field ('{name}') to match the "
                f"parent directory ('{parent_dir}'). This skill would not "
                f"load in VS Code/Copilot."
            ),
        )]
    return []


def check_unverified_fields(skill: ParsedSkill) -> list[Diagnostic]:
    """Note fields whose behavior in Codex and Cursor is unverified."""
    diagnostics: list[Diagnostic] = []
    for field in skill.frontmatter:
        compat = config.COMPAT_MATRIX.get(field)
        if compat is None:
            continue
        unknown_agents = [
            agent for agent, status in compat.items()
            if status == "unknown"
        ]
        if unknown_agents:
            agents_str = ", ".join(sorted(unknown_agents))
            diagnostics.append(Diagnostic(
                rule="compat.unverified",
                severity=Severity.INFO,
                message=(
                    f"Behavior of field '{field}' in {agents_str} is unverified."
                ),
            ))
    return diagnostics


def make_strict_vscode_rule() -> Callable[[ParsedSkill], list[Diagnostic]]:
    """Return a rule that promotes VS Code compat issues to ERROR severity."""

    def check_strict_vscode(skill: ParsedSkill) -> list[Diagnostic]:
        name = skill.frontmatter.get("name")
        if name is None:
            return []
        name = str(name)
        if not name:
            return []
        parent_dir = skill.path.parent.name
        if parent_dir and parent_dir != name:
            return [Diagnostic(
                rule="compat.vscode-dirname",
                severity=Severity.ERROR,
                message=(
                    f"VS Code requires the name field ('{name}') to match the "
                    f"parent directory ('{parent_dir}'). This skill will not "
                    f"load in VS Code/Copilot."
                ),
            )]
        return []

    check_strict_vscode.__name__ = "check_strict_vscode"
    return check_strict_vscode
