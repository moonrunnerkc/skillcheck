"""Configuration loading for skillcheck.toml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover, exercised only on Python 3.10
    tomllib = None


@dataclass(frozen=True, slots=True)
class SkillcheckConfig:
    """Configuration values loaded from skillcheck.toml.

    All fields are optional so command-line flags can override them cleanly.
    """

    format: str | None = None
    max_lines: int | None = None
    max_tokens: int | None = None
    min_desc_score: int | None = None
    target_agent: str | None = None
    strict_vscode: bool | None = None
    strict_cursor: bool | None = None
    strict_all: bool | None = None
    skip_dirname_check: bool | None = None
    skip_ref_check: bool | None = None
    ignore: tuple[str, ...] = ()
    analyze_graph: bool | None = None
    semantic: bool | None = None
    history: bool | None = None
    critique_agent: str | None = None
    graph_agent: str | None = None
    extension_fields: frozenset[str] = frozenset()
    reserved_words: tuple[str, ...] | None = None


class ConfigError(Exception):
    """Raised when skillcheck.toml exists but cannot be parsed or validated."""


_KEY_MAP = {
    "format": "format",
    "max-lines": "max_lines",
    "max_lines": "max_lines",
    "max-tokens": "max_tokens",
    "max_tokens": "max_tokens",
    "min-desc-score": "min_desc_score",
    "min_desc_score": "min_desc_score",
    "target-agent": "target_agent",
    "target_agent": "target_agent",
     "strict-vscode": "strict_vscode",
     "strict_vscode": "strict_vscode",
     "strict-cursor": "strict_cursor",
     "strict_cursor": "strict_cursor",
     "strict-all": "strict_all",
     "strict_all": "strict_all",
    "skip-dirname-check": "skip_dirname_check",
    "skip_dirname_check": "skip_dirname_check",
    "skip-ref-check": "skip_ref_check",
    "skip_ref_check": "skip_ref_check",
    "ignore": "ignore",
    "analyze-graph": "analyze_graph",
    "analyze_graph": "analyze_graph",
    "semantic": "semantic",
    "history": "history",
    "critique-agent": "critique_agent",
    "critique_agent": "critique_agent",
    "graph-agent": "graph_agent",
    "graph_agent": "graph_agent",
}

_INT_FIELDS = {"max_lines", "max_tokens", "min_desc_score"}
_BOOL_FIELDS = {"strict_vscode", "strict_cursor", "strict_all", "skip_dirname_check", "skip_ref_check", "analyze_graph", "semantic", "history"}
_STR_FIELDS = {"format", "target_agent", "critique_agent", "graph_agent"}


def find_config(start: Path) -> Path | None:
    """Find skillcheck.toml from a path or one of its parents.

    Args:
        start: File or directory path used as the search anchor.

    Returns:
        Path to skillcheck.toml, or None when not found.
    """
    current = start if start.is_dir() else start.parent
    for directory in (current, *current.parents):
        candidate = directory / "skillcheck.toml"
        if candidate.exists():
            return candidate
    return None


def _parse_without_tomllib(raw: str) -> dict[str, Any]:
    """Parse a minimal TOML subset for Python 3.10 fallback.

    Supports top-level key/value pairs with strings, booleans, integers, and
    string arrays, plus [frontmatter] for extension fields. That covers
    skillcheck's configuration surface.
    """
    parsed: dict[str, Any] = {}
    current = parsed
    for line_no, raw_line in enumerate(raw.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            if not line.endswith("]"):
                raise ConfigError(f"skillcheck.toml line {line_no} has an invalid section header.")
            section = line[1:-1].strip()
            if section != "frontmatter":
                raise ConfigError(
                    f"skillcheck.toml line {line_no} uses unsupported section '[{section}]'."
                )
            frontmatter = parsed.setdefault("frontmatter", {})
            if not isinstance(frontmatter, dict):
                raise ConfigError("Config section 'frontmatter' must be a table.")
            current = frontmatter
            continue
        if "=" not in line:
            raise ConfigError(f"skillcheck.toml line {line_no} is missing '='.")
        key, value_raw = [part.strip() for part in line.split("=", 1)]
        if value_raw in {"true", "false"}:
            current[key] = value_raw == "true"
        elif value_raw.startswith('"') and value_raw.endswith('"'):
            current[key] = value_raw[1:-1]
        elif value_raw.startswith("[") and value_raw.endswith("]"):
            items = []
            inner = value_raw[1:-1].strip()
            if inner:
                for item in inner.split(","):
                    item = item.strip()
                    if not (item.startswith('"') and item.endswith('"')):
                        raise ConfigError(
                            f"skillcheck.toml line {line_no} array values must be quoted strings."
                        )
                    items.append(item[1:-1])
            current[key] = items
        else:
            try:
                current[key] = int(value_raw)
            except ValueError as exc:
                raise ConfigError(
                    f"skillcheck.toml line {line_no} value for '{key}' must be a string, integer, boolean, or string array."
                ) from exc
    return parsed


def load_config(path: Path | None) -> SkillcheckConfig:
    """Load and validate a skillcheck.toml file.

    Args:
        path: Config path, or None for an empty config.

    Returns:
        Validated SkillcheckConfig.

    Raises:
        ConfigError: If the file cannot be read, parsed, or validated.
    """
    if path is None:
        return SkillcheckConfig()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Cannot read {path}: {exc}. Check file permissions and retry.") from exc

    try:
        data = tomllib.loads(raw) if tomllib is not None else _parse_without_tomllib(raw)
    except ConfigError:
        raise
    except Exception as exc:
        raise ConfigError(f"Cannot parse {path}: {exc}. Fix the TOML syntax and retry.") from exc

    values: dict[str, Any] = {}
    frontmatter = data.pop("frontmatter", {})
    if not isinstance(frontmatter, dict):
        raise ConfigError("Config section 'frontmatter' must be a table.")
    for raw_key, value in frontmatter.items():
        if raw_key == "extension_fields":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ConfigError("Config key 'frontmatter.extension_fields' must be an array of strings.")
            values["extension_fields"] = frozenset(value)
        elif raw_key == "reserved_words":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ConfigError("Config key 'frontmatter.reserved_words' must be an array of strings.")
            values["reserved_words"] = tuple(value)
        else:
            raise ConfigError(f"Unknown config key 'frontmatter.{raw_key}' in {path}.")

    for raw_key, value in data.items():
        field = _KEY_MAP.get(raw_key)
        if field is None:
            raise ConfigError(f"Unknown config key '{raw_key}' in {path}; remove it or use a supported skillcheck option.")
        if field in _INT_FIELDS:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ConfigError(f"Config key '{raw_key}' must be an integer.")
            values[field] = value
        elif field in _BOOL_FIELDS:
            if not isinstance(value, bool):
                raise ConfigError(f"Config key '{raw_key}' must be true or false.")
            values[field] = value
        elif field in _STR_FIELDS:
            if not isinstance(value, str):
                raise ConfigError(f"Config key '{raw_key}' must be a string.")
            values[field] = value
        elif field == "ignore":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ConfigError("Config key 'ignore' must be an array of strings.")
            values[field] = tuple(value)

    return SkillcheckConfig(**values)
