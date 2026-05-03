from __future__ import annotations

import re

# Detects ``## name:`` style markdown headings inside the frontmatter block.
# The heading variant is what fails: PyYAML drops the leading ``#`` as a
# comment, so the field never lands in the parsed mapping.
_FRONTMATTER_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(\w+)\s*:", re.MULTILINE)


def _field_line(raw_text: str, field: str) -> int | None:
    """Return the 1-based line number where a frontmatter field appears.

    Only searches within the frontmatter block to avoid false positives from
    body content that happens to start with a field name.
    """
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i, line in enumerate(lines[1:], 2):
        if line.strip() == "---":
            break
        if line.lstrip().startswith(f"{field}:"):
            return i
    return None


def _frontmatter_block(raw_text: str) -> str | None:
    """Return the raw YAML body between the leading and closing ``---``.

    Returns None when no frontmatter block is found.
    """
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    collected: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            return "\n".join(collected)
        collected.append(line)
    return None


def _heading_for_field(raw_text: str, field: str) -> bool:
    """Return True when ``field`` appears as a ``## name:`` markdown heading.

    The frontmatter block is scanned only; body headings do not trigger.
    """
    block = _frontmatter_block(raw_text)
    if block is None:
        return False
    for match in _FRONTMATTER_HEADING_RE.finditer(block):
        if match.group(1) == field:
            return True
    return False


def _markdown_heading_hint(field: str) -> str:
    """Return the appended hint for a ``## field:`` heading inside frontmatter."""
    return (
        f" hint: found '## {field}:' as a markdown heading inside frontmatter. "
        f"Frontmatter keys are YAML, not markdown. Use '{field}: value' (no '##')."
    )
