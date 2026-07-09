"""Shared hardening helpers for ingested agent responses.

Critique and graph responses are untrusted input: an agent (or whatever fed
the agent) can put anything in the JSON. Two risks are handled here.

1. Terminal control characters. Ingested strings are printed into the
   human-readable report. A response carrying raw ANSI escapes (ESC, 0x1B)
   could forge output, e.g. a fake ``PASS`` line or a cleared screen.
   ``sanitize_ingested_text`` replaces each C0 control char, DEL, and C1
   control char with its visible backslash-escaped form so the content stays
   inert without being silently dropped.

The JSON output path is already safe: ``json.dumps`` escapes control
characters, so sanitization is applied only where text reaches the terminal.
"""

from __future__ import annotations

import re

# C0 controls (0x00-0x1F), DEL (0x7F), and C1 controls (0x80-0x9F). These carry
# ANSI/terminal escape sequences; ESC (0x1B) is the one that matters most.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def sanitize_ingested_text(text: str) -> str:
    """Return *text* with terminal control characters escaped to a visible form.

    Each control character is replaced by its Python backslash escape (ESC
    becomes the four visible characters ``\\x1b``, a newline becomes ``\\n``),
    so a malicious response cannot emit raw escape sequences or break out of a
    single report line.

    Args:
        text: A string taken from an ingested agent response.

    Returns:
        The same text with every control character rendered inert.
    """
    return _CONTROL_CHARS_RE.sub(lambda m: repr(m.group(0))[1:-1], text)
