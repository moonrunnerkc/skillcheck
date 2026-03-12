"""Progressive disclosure budget validation for SKILL.md.

The agentskills.io spec recommends three tiers of content:
- Metadata (frontmatter): ~100 tokens
- Instructions (body): <5000 tokens
- Resources (referenced files): loaded on demand

This module validates that content sits in the right tier and flags
bloat patterns that belong in referenced files, not the main body.
"""

from __future__ import annotations

import re

from skillcheck import config
from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity
from skillcheck.tokenizer import estimate_tokens

# Matches fenced code blocks (``` or ~~~) and captures their content lines.
_CODE_BLOCK_RE = re.compile(
    r"^(?:```|~~~)[^\n]*\n(.*?)^(?:```|~~~)\s*$",
    re.MULTILINE | re.DOTALL,
)

# Matches markdown table rows (lines starting with |).
_TABLE_ROW_RE = re.compile(r"^\|.*\|$", re.MULTILINE)

# Matches base64-encoded content (long strings of base64 characters).
# To avoid false positives on hex hashes (all-lowercase a-f0-9), repeated
# single characters, or API keys, we use a two-step check:
#   1. A candidate regex matches 64+ characters from the base64 alphabet.
#   2. A validator function confirms the candidate contains BOTH uppercase
#      and lowercase letters — a hallmark of real base64 (RFC 4648).
_BASE64_CANDIDATE_RE = re.compile(r"[A-Za-z0-9+/]{64,}={0,2}")


def _is_real_base64(text: str) -> bool:
    """Return True if *text* looks like genuine base64 (mixed case)."""
    has_upper = any(c.isupper() for c in text)
    has_lower = any(c.islower() for c in text)
    return has_upper and has_lower


def _extract_frontmatter_text(raw_text: str) -> str:
    """Extract the raw YAML frontmatter text (between --- delimiters)."""
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    fm_lines: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        fm_lines.append(line)
    return "\n".join(fm_lines)


def check_metadata_budget(skill: ParsedSkill) -> list[Diagnostic]:
    """Warn when frontmatter exceeds the ~100 token metadata budget."""
    fm_text = _extract_frontmatter_text(skill.raw_text)
    if not fm_text:
        return []

    token_count = estimate_tokens(fm_text)
    if token_count > config.METADATA_TOKEN_BUDGET:
        return [Diagnostic(
            rule="disclosure.metadata-budget",
            severity=Severity.WARNING,
            message=(
                f"Frontmatter uses ~{token_count} tokens, exceeding the "
                f"recommended ~{config.METADATA_TOKEN_BUDGET}-token metadata budget. "
                f"Keep metadata concise; move details to the body."
            ),
        )]
    return []


def check_body_budget(skill: ParsedSkill) -> list[Diagnostic]:
    """Warn when the body exceeds the 5000-token instruction budget."""
    if not skill.body:
        return []

    token_count = estimate_tokens(skill.body)
    if token_count > config.BODY_TOKEN_BUDGET:
        return [Diagnostic(
            rule="disclosure.body-budget",
            severity=Severity.WARNING,
            message=(
                f"Body uses ~{token_count} tokens, exceeding the recommended "
                f"{config.BODY_TOKEN_BUDGET}-token instruction budget. "
                f"Move large content blocks to referenced files in a resources/ directory."
            ),
        )]
    return []


def check_body_bloat(skill: ParsedSkill) -> list[Diagnostic]:
    """Flag content patterns in the body that belong in referenced files."""
    if not skill.body:
        return []

    diagnostics: list[Diagnostic] = []

    # Check for large code blocks
    for match in _CODE_BLOCK_RE.finditer(skill.body):
        block_content = match.group(1)
        line_count = len(block_content.splitlines())
        if line_count > config.BLOAT_CODE_BLOCK_LINES:
            diagnostics.append(Diagnostic(
                rule="disclosure.body-bloat",
                severity=Severity.INFO,
                message=(
                    f"Code block with {line_count} lines found in body. "
                    f"Blocks over {config.BLOAT_CODE_BLOCK_LINES} lines should be "
                    f"moved to a referenced file."
                ),
            ))

    # Check for large tables
    table_rows = _TABLE_ROW_RE.findall(skill.body)
    # Subtract separator rows (containing only |, -, :, and spaces)
    data_rows = [r for r in table_rows if not re.match(r"^\|[\s:|-]+\|$", r)]
    if len(data_rows) > config.BLOAT_TABLE_ROWS:
        diagnostics.append(Diagnostic(
            rule="disclosure.body-bloat",
            severity=Severity.INFO,
            message=(
                f"Table with {len(data_rows)} data rows found in body. "
                f"Tables over {config.BLOAT_TABLE_ROWS} rows should be "
                f"moved to a referenced file."
            ),
        ))

    # Check for base64 content (two-step: candidate match + mixed-case validation)
    match = _BASE64_CANDIDATE_RE.search(skill.body)
    if match and _is_real_base64(match.group()):
        diagnostics.append(Diagnostic(
            rule="disclosure.body-bloat",
            severity=Severity.INFO,
            message=(
                "Base64-encoded content found in body. "
                "Move binary data to a referenced file."
            ),
        ))

    return diagnostics
