"""Activation hypothesis generation for SKILL.md discoverability analysis.

The generator is intentionally heuristic. Agents do not publish routing
algorithms, so these phrases are informed estimates, not guarantees.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from skillcheck.parser import ParsedSkill


@dataclass(frozen=True, slots=True)
class ActivationHypothesis:
    """One possible natural-language trigger for a skill.

    Args:
        phrase: Trigger phrase likely to route to the skill.
        score: Relative confidence score in the range 0-100.
        rationale: Short reason the phrase was generated.
    """

    phrase: str
    score: int
    rationale: str


@dataclass(frozen=True, slots=True)
class ActivationReport:
    """Activation analysis output for a skill.

    Args:
        skill_name: Name from frontmatter.
        entropy: Shannon entropy over generated hypothesis scores.
        hypotheses: Generated trigger hypotheses.
    """

    skill_name: str
    entropy: float
    hypotheses: tuple[ActivationHypothesis, ...]


_STOPWORDS = frozenset({
    "a",
    "an",
    "and",
    "against",
    "as",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "use",
    "uses",
    "when",
    "with",
})

_ACTION_VERBS = frozenset({
    "analyze",
    "build",
    "check",
    "create",
    "debug",
    "evaluate",
    "extract",
    "generate",
    "implement",
    "lint",
    "review",
    "score",
    "summarize",
    "test",
    "validate",
    "verify",
})

_HEADING_RE = re.compile(r"^#{2,3}\s+(.+)$", re.MULTILINE)
_WORD_RE = re.compile(r"[a-z][a-z0-9-]{2,}", re.IGNORECASE)


def _clean_phrase(text: str) -> str:
    words = _WORD_RE.findall(text.lower())
    return " ".join(w for w in words if w not in _STOPWORDS)


def _keywords(text: str, limit: int = 8) -> list[str]:
    counts: dict[str, int] = {}
    for word in _WORD_RE.findall(text.lower()):
        if word in _STOPWORDS or len(word) < 3:
            continue
        counts[word] = counts.get(word, 0) + 1
    return [word for word, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def _entropy(scores: list[int]) -> float:
    total = sum(scores)
    if total <= 0:
        return 0.0
    value = 0.0
    for score in scores:
        probability = score / total
        if probability > 0:
            value -= probability * math.log2(probability)
    return round(value, 3)


def _dedupe(hypotheses: list[ActivationHypothesis]) -> tuple[ActivationHypothesis, ...]:
    seen: set[str] = set()
    unique: list[ActivationHypothesis] = []
    for hypothesis in hypotheses:
        key = hypothesis.phrase.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(hypothesis)
    return tuple(unique)


def generate_activation_hypotheses(skill: ParsedSkill, limit: int = 10) -> ActivationReport:
    """Generate likely activation trigger phrases for a skill.

    Args:
        skill: Parsed SKILL.md document.
        limit: Maximum number of hypotheses to return. Must be at least 1.

    Returns:
        ActivationReport with trigger phrases and entropy score.

    Raises:
        ValueError: If limit is less than 1.
    """
    if limit < 1:
        raise ValueError("Activation hypothesis limit must be at least 1; pass a positive integer.")

    raw_name = skill.frontmatter.get("name", "skill")
    name = raw_name if isinstance(raw_name, str) and raw_name.strip() else "skill"
    description_raw = skill.frontmatter.get("description", "")
    description = description_raw if isinstance(description_raw, str) else ""
    desc_phrase = _clean_phrase(description)
    keywords = _keywords("\n".join([description, skill.body]), limit=8)
    headings = [match.group(1).strip() for match in _HEADING_RE.finditer(skill.body)]

    hypotheses: list[ActivationHypothesis] = []
    if desc_phrase:
        hypotheses.append(ActivationHypothesis(
            phrase=description.strip().rstrip("."),
            score=96,
            rationale="frontmatter description is the primary routing signal",
        ))

    name_words = name.replace("-", " ")
    hypotheses.append(ActivationHypothesis(
        phrase=f"use {name_words}",
        score=88,
        rationale="skill name is an explicit invocation cue",
    ))

    for verb in sorted(_ACTION_VERBS & set(keywords)):
        target_words = [word for word in keywords if word != verb][:3]
        target = " ".join(target_words) if target_words else name_words
        hypotheses.append(ActivationHypothesis(
            phrase=f"{verb} {target}",
            score=82,
            rationale="action verb and domain terms appear in the skill content",
        ))

    for heading in headings[:4]:
        cleaned = _clean_phrase(heading)
        if cleaned:
            hypotheses.append(ActivationHypothesis(
                phrase=cleaned,
                score=70,
                rationale="section heading describes an executable capability",
            ))

    if keywords:
        hypotheses.append(ActivationHypothesis(
            phrase=f"help with {' '.join(keywords[:4])}",
            score=64,
            rationale="high-frequency domain terms indicate likely user intent",
        ))

    deduped = _dedupe(hypotheses)[:limit]
    return ActivationReport(
        skill_name=name,
        entropy=_entropy([h.score for h in deduped]),
        hypotheses=deduped,
    )
