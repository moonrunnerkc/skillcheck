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

KNOWN_FRONTMATTER_FIELDS: frozenset[str] = frozenset({
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
