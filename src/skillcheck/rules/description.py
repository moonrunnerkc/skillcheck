"""Description quality scoring for SKILL.md discoverability.

Scores the description field 0-100 across five dimensions:
- Action verb presence (does the description lead with a verb?)
- Trigger phrase detection (does it say when to activate?)
- Keyword density (specific terms vs. generic filler)
- Specificity (avoids vague words without qualifiers)
- Length adequacy (not too short, not too long)

This is the high-value feature no other tool provides. Agents use descriptions
to decide whether to activate a skill. A low score means the skill is invisible.
"""

from __future__ import annotations

import re

from skillcheck.parser import ParsedSkill
from skillcheck.result import Diagnostic, Severity

# Common third-person / imperative action verbs that signal clear skill intent.
_ACTION_VERBS = frozenset({
    "generates", "analyzes", "validates", "deploys", "processes",
    "creates", "builds", "converts", "extracts", "formats",
    "monitors", "scans", "parses", "transforms", "compiles",
    "tests", "checks", "lints", "runs", "executes",
    "fetches", "sends", "uploads", "downloads",
    "configures", "sets", "updates", "installs", "removes",
    "detects", "identifies", "classifies", "scores", "ranks",
    "summarizes", "translates", "encrypts", "decrypts",
    "automates", "scaffolds", "provisions", "migrates", "syncs",
    "generate", "analyze", "validate", "deploy", "process",
    "create", "build", "convert", "extract", "format",
    "monitor", "scan", "parse", "transform", "compile",
    "test", "check", "lint", "run", "execute",
    "fetch", "send", "upload", "download",
    "configure", "set", "update", "install", "remove",
    "detect", "identify", "classify", "score", "rank",
    "summarize", "translate", "encrypt", "decrypt",
    "automate", "scaffold", "provision", "migrate", "sync",
})

# Trigger phrases that signal when a skill should activate.
_TRIGGER_PATTERNS = [
    re.compile(r"\buse\s+(?:this\s+)?(?:skill\s+)?when\b", re.IGNORECASE),
    re.compile(r"\bactivate\s+(?:this\s+)?(?:skill\s+)?(?:for|when)\b", re.IGNORECASE),
    re.compile(r"\brun\s+(?:this\s+)?(?:skill\s+)?when\b", re.IGNORECASE),
    re.compile(r"\binvoke\s+(?:this\s+)?(?:skill\s+)?when\b", re.IGNORECASE),
    re.compile(r"\bwhenever\s+(?:the\s+)?user\s+(?:mentions?|asks?|requests?|needs?|wants?)\b", re.IGNORECASE),
    re.compile(r"\bmake\s+sure\s+to\s+use\s+this\s+skill\b", re.IGNORECASE),
    re.compile(r"\btrigger(?:s|ed)?\s+(?:when|for|by)\b", re.IGNORECASE),
]

# Generic filler words that reduce specificity.
_VAGUE_WORDS = frozenset({
    "tool", "helper", "utility", "stuff", "things", "various",
    "general", "generic", "simple", "basic", "easy", "nice",
    "good", "great", "awesome", "cool", "helpful", "useful",
    "important", "powerful", "flexible", "robust", "comprehensive",
    "efficient", "effective", "handles",
})

# Common stop words excluded from keyword density calculation.
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "shall", "should", "may", "might", "must", "can",
    "could", "of", "in", "to", "for", "with", "on", "at", "from",
    "by", "about", "as", "into", "through", "during", "before",
    "after", "above", "below", "between", "under", "again",
    "further", "then", "once", "and", "but", "or", "nor", "not",
    "so", "yet", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "only", "own", "same", "than", "too",
    "very", "just", "because", "if", "when", "where", "how",
    "all", "any", "this", "that", "these", "those", "it", "its",
})


def _score_action_verbs(desc: str) -> tuple[int, str | None]:
    """Score 0-25 based on action verb presence, especially at the start."""
    words = re.findall(r"[a-zA-Z]+", desc)
    if not words:
        return 0, "Description has no words."

    first_word = words[0].lower()
    has_leading_verb = first_word in _ACTION_VERBS
    verb_count = sum(1 for w in words if w.lower() in _ACTION_VERBS)

    if has_leading_verb and verb_count >= 2:
        return 25, None
    if has_leading_verb:
        return 20, None
    if verb_count >= 2:
        return 15, "Start the description with an action verb (e.g., 'Generates...', 'Validates...')."
    if verb_count == 1:
        return 10, "Start the description with an action verb (e.g., 'Generates...', 'Validates...')."
    return 0, "No action verbs found. Use verbs like 'Generates', 'Analyzes', 'Validates'."


def _score_trigger_phrases(desc: str) -> tuple[int, str | None]:
    """Score 0-25 based on trigger phrase presence."""
    matches = sum(1 for p in _TRIGGER_PATTERNS if p.search(desc))
    if matches >= 2:
        return 25, None
    if matches == 1:
        return 20, None
    # Check for weaker contextual signals
    weak_signals = [
        re.compile(r"\bfor\s+\w+ing\b", re.IGNORECASE),
        re.compile(r"\bto\s+\w+\b", re.IGNORECASE),
    ]
    weak = sum(1 for p in weak_signals if p.search(desc))
    if weak:
        return 10, "Add explicit trigger phrases like 'Use when...' or 'Activate for...'."
    return 0, "No trigger context found. Add phrases like 'Use this skill whenever the user mentions...'."


def _score_keyword_density(desc: str) -> tuple[int, str | None]:
    """Score 0-25 based on the ratio of content words to total words."""
    words = re.findall(r"[a-zA-Z]+", desc)
    if not words:
        return 0, "Description is empty."

    content_words = [w for w in words if w.lower() not in _STOP_WORDS]
    ratio = len(content_words) / len(words) if words else 0

    if ratio >= 0.6:
        return 25, None
    if ratio >= 0.45:
        return 20, None
    if ratio >= 0.3:
        return 15, "Replace filler words with domain-specific keywords."
    return 5, "Description is mostly filler. Use specific terms for the task domain."


def _score_specificity(desc: str) -> tuple[int, str | None]:
    """Score 0-15 based on absence of vague words and presence of concrete terms."""
    words = [w.lower() for w in re.findall(r"[a-zA-Z]+", desc)]
    if not words:
        return 0, "Description is empty."

    vague_count = sum(1 for w in words if w in _VAGUE_WORDS)
    vague_ratio = vague_count / len(words) if words else 0

    if vague_ratio == 0:
        return 15, None
    if vague_ratio <= 0.1:
        return 10, None
    if vague_ratio <= 0.2:
        return 5, f"Reduce vague terms ({vague_count} found). Be specific about what the skill does."
    return 0, f"Too many vague words ({vague_count} found: 'tool', 'helper', etc.). Name the exact actions and domains."


def _score_length(desc: str) -> tuple[int, str | None]:
    """Score 0-10 based on description length adequacy."""
    length = len(desc.strip())
    if length < 20:
        return 0, f"Description is too short ({length} chars). Provide enough detail for agent routing."
    if length < 40:
        return 3, "Description is short. Add more context about when to use this skill."
    if length > 500:
        return 3, f"Description is long ({length} chars). Keep it concise; move details to the body."
    if length > 300:
        return 7, "Description is getting long. Consider trimming to the essentials."
    # 40-300 chars is the sweet spot
    return 10, None


def score_description(desc: str) -> tuple[int, list[str]]:
    """Score a description string from 0-100 with improvement suggestions.

    Returns (score, suggestions) where suggestions is a list of actionable strings.
    """
    scorers = [
        _score_action_verbs,
        _score_trigger_phrases,
        _score_keyword_density,
        _score_specificity,
        _score_length,
    ]
    total = 0
    suggestions: list[str] = []
    for scorer in scorers:
        points, suggestion = scorer(desc)
        total += points
        if suggestion:
            suggestions.append(suggestion)
    return total, suggestions


def check_description_quality(skill: ParsedSkill) -> list[Diagnostic]:
    """Score description quality and return an INFO diagnostic with the result."""
    desc = skill.frontmatter.get("description")
    if not desc or not isinstance(desc, str) or not desc.strip():
        return []  # Missing/empty descriptions are handled by frontmatter rules.

    score, suggestions = score_description(desc)

    suggestion_text = ""
    if suggestions:
        suggestion_text = " Suggestions: " + "; ".join(suggestions)

    return [Diagnostic(
        rule="description.quality-score",
        severity=Severity.INFO,
        message=f"Description quality score: {score}/100.{suggestion_text}",
    )]


def make_min_score_rule(
    min_score: int,
) -> callable:
    """Return a rule that errors/warns when description score falls below threshold."""

    def check_description_min_score(skill: ParsedSkill) -> list[Diagnostic]:
        desc = skill.frontmatter.get("description")
        if not desc or not isinstance(desc, str) or not desc.strip():
            return []

        score, suggestions = score_description(desc)
        if score >= min_score:
            return []

        suggestion_text = ""
        if suggestions:
            suggestion_text = " " + "; ".join(suggestions)

        return [Diagnostic(
            rule="description.min-score",
            severity=Severity.WARNING,
            message=(
                f"Description quality score {score}/100 is below the "
                f"minimum threshold of {min_score}.{suggestion_text}"
            ),
        )]

    check_description_min_score.__name__ = "check_description_min_score"
    return check_description_min_score
