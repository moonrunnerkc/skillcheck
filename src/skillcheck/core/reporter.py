"""Rich reasoning-trace reporter module for skillcheck v1.0."""

from __future__ import annotations

from skillcheck.result import ValidationResult


REPORTER_STUB_MESSAGE = "Reasoning-trace reporting lands in v1.0."


def render_markdown_report(result: ValidationResult) -> str:
    """Render a validation result into markdown.

    Args:
        result: Validation result to render.

    Returns:
        Markdown report content.

    Raises:
        NotImplementedError: Always raised in Phase 0 scaffolding.
    """
    raise NotImplementedError(REPORTER_STUB_MESSAGE)


def render_json_report(result: ValidationResult) -> dict[str, object]:
    """Render a validation result into a structured JSON payload.

    Args:
        result: Validation result to render.

    Returns:
        JSON-serializable report payload.

    Raises:
        NotImplementedError: Always raised in Phase 0 scaffolding.
    """
    raise NotImplementedError(REPORTER_STUB_MESSAGE)
