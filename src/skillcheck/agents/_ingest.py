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

import json
import re

from skillcheck.agents._response_text import strip_response_noise

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


def decode_json_or_raise(raw: str, error_cls: type[Exception]) -> object:
    """Strip response noise, parse JSON, or raise *error_cls* on failure.

    Shared by the critique and graph parsers. The error message names the
    decoder's position and the first 200 characters received (newlines
    collapsed) so callers get context without dumping the full response.

    Args:
        raw: Raw agent response (may include markdown fences or prose preamble).
        error_cls: Parser-specific JSON-error type to raise (CritiqueJSONError,
            GraphJSONError).

    Returns:
        The decoded JSON value (dict, list, or scalar; callers type-check it).

    Raises:
        error_cls: When the cleaned text is not valid JSON. The original
            JSONDecodeError is preserved as the cause.
    """
    cleaned = strip_response_noise(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as err:
        preview = raw[:200].replace("\n", " ")
        raise error_cls(
            f"Response is not valid JSON (error at position {err.pos}): "
            f"first 200 chars: {preview!r}"
        ) from err


def require_field(
    obj: dict[str, object],
    key: str,
    expected_type: type | tuple[type, ...],
    *,
    error_cls: type[Exception],
    context: str = "",
) -> object:
    """Extract a required field from *obj* with type checking.

    Shared by the critique and graph parsers. ``bool`` is rejected for ``int``
    fields (and for ``(int, None)`` unions), since it is an int subclass but
    never a valid score or line number.

    Args:
        obj: Mapping to extract from.
        key: Required field name.
        expected_type: Acceptable Python type, or a tuple of types for a union.
        error_cls: Parser-specific schema-error type to raise (CritiqueSchemaError,
            GraphSchemaError).
        context: Optional prefix for error messages, e.g. "findings[0]".

    Returns:
        The field value.

    Raises:
        error_cls: If the field is missing, has the wrong type, or is a bool
            where an int is required.
    """
    full_key = f"{context}.{key}" if context else key
    if key not in obj:
        raise error_cls(f"Missing required field '{full_key}'")
    value = obj[key]
    if expected_type is int and isinstance(value, bool):
        raise error_cls(f"Field '{full_key}' must be int, got bool: {value!r}")
    if (
        isinstance(expected_type, tuple)
        and int in expected_type
        and isinstance(value, bool)
    ):
        raise error_cls(f"Field '{full_key}' must be int or null, got bool: {value!r}")
    if not isinstance(value, expected_type):
        if isinstance(expected_type, tuple):
            type_name = " or ".join(
                "null" if t is type(None) else t.__name__ for t in expected_type
            )
        else:
            type_name = expected_type.__name__
        raise error_cls(
            f"Field '{full_key}' must be {type_name}, "
            f"got {type(value).__name__}: {value!r}"
        )
    return value


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
