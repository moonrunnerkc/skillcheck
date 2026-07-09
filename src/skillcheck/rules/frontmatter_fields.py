from __future__ import annotations

import yaml

from skillcheck import config
from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity
from skillcheck.rules.frontmatter_common import _field_line, _frontmatter_block


def check_unknown_fields(skill: ParsedSkill) -> list[Diagnostic]:
    diagnostics = []
    for field in skill.frontmatter:
        field_name = str(field)
        if field_name in config.SPEC_FIELDS or field_name in config.extension_fields:
            continue
        if field_name in config.ECOSYSTEM_FIELDS:
            diagnostics.append(Diagnostic(
                rule="frontmatter.field.ecosystem",
                severity=Severity.INFO,
                message=(
                    f"Field '{field_name}' is ecosystem-common but not in the "
                    f"agentskills.io spec. Add it to skillcheck.toml under "
                    f"[frontmatter] extension_fields if intentional."
                ),
                line=_field_line(skill.raw_text, field_name),
                context=f"{field_name}: ...",
                source="advisory",
                confidence="medium",
            ))
            continue
        diagnostics.append(Diagnostic(
            rule="frontmatter.field.unknown",
            severity=Severity.WARNING,
            message=(
                f"Unknown frontmatter field '{field_name}'. "
                f"Known fields: {', '.join(sorted(config.SPEC_FIELDS))}."
            ),
            line=_field_line(skill.raw_text, field_name),
            context=f"{field_name}: ...",
        ))
    return diagnostics


def _collect_anchor_names(fm_raw: str) -> list[str]:
    """Return the anchor names declared or referenced in the frontmatter.

    Uses the YAML event stream so only real anchors/aliases are seen. A ``&`` or
    ``*`` inside a quoted scalar (e.g. ``"Reviews R&D notes and *only* flags..."``)
    is part of the value, not an anchor, so it is not reported. Scalar and
    collection-start events carry ``.anchor`` for a declaration; alias events
    carry ``.anchor`` for a reference; both are collected.
    """
    try:
        events = yaml.parse(fm_raw, Loader=yaml.SafeLoader)
        anchors = [anchor for event in events if (anchor := getattr(event, "anchor", None))]
    except yaml.YAMLError:
        return []
    return sorted(set(anchors))


def check_yaml_anchors(skill: ParsedSkill) -> list[Diagnostic]:
    """Warn when YAML anchors or aliases are used in frontmatter."""
    fm_raw = _frontmatter_block(skill.raw_text)
    if not fm_raw:
        return []

    names = _collect_anchor_names(fm_raw)
    if not names:
        return []

    return [Diagnostic(
        rule="frontmatter.yaml-anchors",
        severity=Severity.WARNING,
        message=(
            f"YAML anchors/aliases detected in frontmatter ({', '.join(names)}). "
            f"Anchors silently copy values between fields, which can bypass "
            f"validation. Use explicit values instead."
        ),
    )]
