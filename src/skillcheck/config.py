from collections.abc import Iterable, Mapping
from types import MappingProxyType

MAX_BODY_LINES: int = 500
MAX_TOKENS: int = 8000

NAME_MAX_LENGTH: int = 64
DESCRIPTION_MAX_LENGTH: int = 1024

# Progressive disclosure token budgets (agentskills.io spec)
METADATA_TOKEN_BUDGET: int = 100
BODY_TOKEN_BUDGET: int = 5000

# Description quality scoring
DEFAULT_MIN_DESC_SCORE: int = 0  # no enforcement by default

# Bloat detection thresholds
BLOAT_CODE_BLOCK_LINES: int = 50
BLOAT_TABLE_ROWS: int = 20

SPEC_FIELDS: frozenset[str] = frozenset({
    "name",
    "description",
    "version",
    "author",
    "tags",
    "allowed-tools",
    "model",
    "context",
    "agent",
    "hooks",
    "user-invocable",
    "disable-model-invocation",
    "skills",
    "mode",
})

ECOSYSTEM_FIELDS: frozenset[str] = frozenset({
    "license",
    "metadata",
    "repository",
    "homepage",
    "template",
})

extension_fields: frozenset[str] = frozenset()


def set_extension_fields(fields: Iterable[str]) -> None:
    global extension_fields
    extension_fields = frozenset(fields)


# Default name reserved-word list.  Skill name substrings that may collide
# with platform-reserved namespaces.  Configurable via
# [frontmatter] reserved_words in skillcheck.toml; the loader installs the
# user's list via set_reserved_words.
DEFAULT_RESERVED_WORDS: tuple[str, ...] = ("anthropic", "claude")

reserved_words: tuple[str, ...] = DEFAULT_RESERVED_WORDS


def set_reserved_words(words: Iterable[str]) -> None:
    global reserved_words
    coerced = tuple(w.lower() for w in words)
    reserved_words = coerced if coerced else DEFAULT_RESERVED_WORDS


# Cross-agent compatibility matrix.
# Each field maps to a dict of agent -> support status.
# Statuses: "supported", "ignored", "unknown"
COMPAT_MATRIX: dict[str, dict[str, str]] = {
    "name":                     {"claude": "supported", "vscode": "supported", "codex": "supported", "cursor": "supported"},
    "description":              {"claude": "supported", "vscode": "supported", "codex": "supported", "cursor": "supported"},
    "version":                  {"claude": "supported", "vscode": "supported", "codex": "unknown",   "cursor": "unknown"},
    "author":                   {"claude": "supported", "vscode": "supported", "codex": "unknown",   "cursor": "unknown"},
    "tags":                     {"claude": "supported", "vscode": "supported", "codex": "unknown",   "cursor": "unknown"},
    "allowed-tools":            {"claude": "supported", "vscode": "supported", "codex": "unknown",   "cursor": "unknown"},
    "user-invocable":           {"claude": "supported", "vscode": "supported", "codex": "unknown",   "cursor": "unknown"},
    "context":                  {"claude": "supported", "vscode": "supported", "codex": "unknown",   "cursor": "unknown"},
    "model":                    {"claude": "supported", "vscode": "ignored",   "codex": "unknown",   "cursor": "unknown"},
    "disable-model-invocation": {"claude": "supported", "vscode": "ignored",   "codex": "unknown",   "cursor": "unknown"},
    "mode":                     {"claude": "supported", "vscode": "ignored",   "codex": "unknown",   "cursor": "unknown"},
    "hooks":                    {"claude": "supported", "vscode": "ignored",   "codex": "unknown",   "cursor": "unknown"},
    "agent":                    {"claude": "supported", "vscode": "ignored",   "codex": "unknown",   "cursor": "unknown"},
    "skills":                   {"claude": "supported", "vscode": "ignored",   "codex": "unknown",   "cursor": "unknown"},
}

# Fields that are only functional in Claude Code
CLAUDE_ONLY_FIELDS: frozenset[str] = frozenset({
    "model",
    "disable-model-invocation",
    "mode",
    "hooks",
    "agent",
    "skills",
})

# Maximum points per description-scoring dimension, in report order.
#
# Single source of truth. `rules.description.score_description` sums against
# these and `--explain-score` renders the denominators from them. They were
# duplicated: the scorer carried its own literals and formatters.py hardcoded a
# second copy, so changing a weight would have left the report showing a stale
# cap ("12/25" against a dimension worth 20).
DESCRIPTION_SCORE_WEIGHTS: Mapping[str, int] = MappingProxyType({
    "action": 25,
    "trigger": 25,
    "keywords": 25,
    "specificity": 15,
    "length": 10,
})
