"""Render activation hypothesis reports."""

from __future__ import annotations

import json

from skillcheck.core.activation import ActivationReport


def render_activation_text(report: ActivationReport) -> str:
    """Render activation hypotheses as plain text.

    Args:
        report: Activation analysis report.

    Returns:
        Human-readable report string.
    """
    lines = [
        f"Activation hypotheses: {report.skill_name}",
        f"Discoverability entropy: {report.entropy:.3f}",
        "Caveat: agent routing algorithms are proprietary; these are estimates, not guarantees.",
        "",
    ]
    for index, hypothesis in enumerate(report.hypotheses, start=1):
        lines.append(f"{index:>2}. {hypothesis.phrase}  score={hypothesis.score}")
        lines.append(f"    {hypothesis.rationale}")
    return "\n".join(lines)


def render_activation_markdown(report: ActivationReport) -> str:
    """Render activation hypotheses as Markdown.

    Args:
        report: Activation analysis report.

    Returns:
        Markdown report string.
    """
    lines = [
        f"# Activation Hypotheses: {report.skill_name}",
        "",
        f"Discoverability entropy: `{report.entropy:.3f}`",
        "",
        "Agent routing algorithms are proprietary. These phrases are informed estimates, not guarantees.",
        "",
        "| # | Phrase | Score | Rationale |",
        "|---:|---|---:|---|",
    ]
    for index, hypothesis in enumerate(report.hypotheses, start=1):
        phrase = hypothesis.phrase.replace("|", "\\|")
        rationale = hypothesis.rationale.replace("|", "\\|")
        lines.append(f"| {index} | {phrase} | {hypothesis.score} | {rationale} |")
    return "\n".join(lines)


def render_activation_json(report: ActivationReport) -> str:
    """Render activation hypotheses as JSON.

    Args:
        report: Activation analysis report.

    Returns:
        JSON report string.
    """
    payload = {
        "skill_name": report.skill_name,
        "entropy": report.entropy,
        "caveat": "Agent routing algorithms are proprietary; these are estimates, not guarantees.",
        "hypotheses": [
            {
                "phrase": hypothesis.phrase,
                "score": hypothesis.score,
                "rationale": hypothesis.rationale,
            }
            for hypothesis in report.hypotheses
        ],
    }
    return json.dumps(payload, indent=2)
