from __future__ import annotations

import re

from skillcheck import config
from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity
from skillcheck.rules.frontmatter_common import _field_line, _frontmatter_block

_YAML_ANCHOR_RE = re.compile(r"&([A-Za-z_][A-Za-z0-9_-]*)")
_YAML_ALIAS_RE = re.compile(r"\*([A-Za-z_][A-Za-z0-9_-]*)")


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


def check_yaml_anchors(skill: ParsedSkill) -> list[Diagnostic]:
    """Warn when YAML anchors or aliases are used in frontmatter."""
    fm_raw = _frontmatter_block(skill.raw_text)
    if not fm_raw:
        return []

    diagnostics: list[Diagnostic] = []
    anchors = _YAML_ANCHOR_RE.findall(fm_raw)
    aliases = _YAML_ALIAS_RE.findall(fm_raw)

    if anchors or aliases:
        names = sorted(set(anchors + aliases))
        diagnostics.append(Diagnostic(
            rule="frontmatter.yaml-anchors",
            severity=Severity.WARNING,
            message=(
                f"YAML anchors/aliases detected in frontmatter ({', '.join(names)}). "
                f"Anchors silently copy values between fields, which can bypass "
                f"validation. Use explicit values instead."
            ),
        ))

    return diagnostics
