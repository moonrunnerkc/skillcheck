from __future__ import annotations


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
