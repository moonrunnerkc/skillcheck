from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Matches an opening ---, YAML content, and closing ---, with optional trailing spaces
# and optional carriage returns for cross-platform compatibility.
_FRONTMATTER_RE = re.compile(
    r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)",
    re.DOTALL,
)


class ParseError(Exception):
    pass


@dataclass(frozen=True)
class ParsedSkill:
    path: Path
    frontmatter: dict[str, Any]
    body: str
    body_lines: int
    raw_text: str


def parse(path: Path) -> ParsedSkill:
    """Load and structurally split a SKILL.md file into frontmatter and body."""
    try:
        # utf-8-sig strips a leading BOM if present
        raw_text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParseError(f"File is not valid UTF-8: {path}") from exc

    match = _FRONTMATTER_RE.match(raw_text)
    if not match:
        body = raw_text
        return ParsedSkill(
            path=path,
            frontmatter={},
            body=body,
            body_lines=len(body.splitlines()),
            raw_text=raw_text,
        )

    try:
        loaded = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ParseError(f"Invalid YAML frontmatter in {path}: {exc}") from exc

    frontmatter = loaded if loaded is not None else {}
    if not isinstance(frontmatter, dict):
        raise ParseError(
            f"Frontmatter must be a YAML mapping, got {type(frontmatter).__name__} in {path}. "
            "Wrap frontmatter in key: value pairs."
        )

    body = raw_text[match.end():]
    return ParsedSkill(
        path=path,
        frontmatter=frontmatter,
        body=body,
        body_lines=len(body.splitlines()),
        raw_text=raw_text,
    )
