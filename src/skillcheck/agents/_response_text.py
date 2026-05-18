"""Shared text-stripping helpers for agent JSON responses.

Both the critique parser and the graph parser receive raw LLM output that
may be wrapped in a markdown code fence or preceded by prose. The cleanup
rules are identical, so they live here and are imported by both parsers.

Stripping rules applied before JSON parsing (in order):
  1. Leading and trailing whitespace.
  2. A single markdown code fence: ```json...``` or ```...``` wrapping the
     entire remaining content. Only one level of fencing is stripped; a
     fence inside the JSON object is left alone.
  3. Any prose before the first '{'. The content is sliced to begin at the
     first occurrence of '{'.

These rules are deterministic and applied in sequence. No regex
substitution happens inside the JSON body itself.
"""
from __future__ import annotations

import re

# Matches a full ```json\n...\n``` or ```\n...\n``` fence wrapping the entire content.
_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


def strip_response_noise(raw: str) -> str:
    """Remove LLM response noise before attempting JSON parsing.

    Stripping steps (applied in order):
    1. Strip leading/trailing whitespace.
    2. Strip a single markdown code fence (```json or ```) wrapping the whole content.
    3. Strip any prose before the first '{'.
    """
    text = raw.strip()

    fence_match = _FENCE_RE.match(text)
    if fence_match:
        text = fence_match.group(1).strip()

    brace_pos = text.find("{")
    if brace_pos > 0:
        text = text[brace_pos:]

    return text
