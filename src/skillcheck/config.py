MAX_BODY_LINES: int = 500
MAX_TOKENS: int = 8000

NAME_MAX_LENGTH: int = 64
DESCRIPTION_MAX_LENGTH: int = 1024

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
})
