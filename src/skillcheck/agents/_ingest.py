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

# Maximum size of a single ingested response (stdin or file). A real critique or
# graph response is a few KB; 5 MiB is a generous ceiling that still bounds a
# hostile or runaway payload.
MAX_INGEST_BYTES = 5 * 1024 * 1024

# Maximum number of items in any single ingested list (findings, missing_context,
# contradictions, capabilities, inputs, outputs, edges). A real response has a
# handful; this bounds a payload that is one enormous list of tiny items.
MAX_INGEST_LIST_ITEMS = 10_000

# C0 controls (0x00-0x1F), DEL (0x7F), and C1 controls (0x80-0x9F). These carry
# ANSI/terminal escape sequences; ESC (0x1B) is the one that matters most.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def enforce_list_cap(count: int, field: str, error_cls: type[Exception]) -> None:
    """Raise *error_cls* if an ingested list exceeds ``MAX_INGEST_LIST_ITEMS``.

    Args:
        count: Number of items in the ingested list.
        field: Field name for the error message, e.g. "findings".
        error_cls: Parser-specific exception type to raise (CritiqueSchemaError,
            GraphSchemaError).

    Raises:
        error_cls: When *count* exceeds the cap. The message names the field,
            the count, and the cap.
    """
    if count > MAX_INGEST_LIST_ITEMS:
        raise error_cls(
            f"Ingested '{field}' has {count} items, over the {MAX_INGEST_LIST_ITEMS}-item cap. "
            f"The response is unreasonably large; trim it or split the run into smaller batches."
        )


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
