"""Every rejection path in skillcheck.toml loading produces a usable message.

The loader validates a lot and almost none of it was asserted: unknown keys,
wrong value types, and malformed TOML all raised ConfigError, but nothing
checked that the message names the offending key or says what to do. A config
error is the first thing a user sees when they misconfigure the tool, and an
unnamed key means reading the loader source to find out which one was wrong.

These are behavior assertions, not coverage padding. Each one pins a message a
user reads.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from skillcheck.config_loader import ConfigError, find_config, load_config


def _config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "skillcheck.toml"
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Unknown keys name themselves
# ---------------------------------------------------------------------------


def test_unknown_top_level_key_is_named(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config(_config(tmp_path, 'max_lines_typo = 200\n'))
    assert "max_lines_typo" in str(exc.value)


def test_unknown_frontmatter_key_is_named(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config(_config(tmp_path, '[frontmatter]\nextention_fields = ["x"]\n'))
    assert "extention_fields" in str(exc.value)


# ---------------------------------------------------------------------------
# Wrong types say which key and what shape is expected
# ---------------------------------------------------------------------------


def test_extension_fields_must_be_a_list_of_strings(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config(_config(tmp_path, "[frontmatter]\nextension_fields = 3\n"))
    assert "extension_fields" in str(exc.value)
    assert "array of strings" in str(exc.value)


def test_extension_fields_rejects_a_list_of_non_strings(tmp_path: Path) -> None:
    """A list is not enough; the members have to be strings.

    On 3.10 the fallback parser rejects it first, naming the line; on 3.11+
    tomllib parses it and the type check rejects it. Both name the problem.
    """
    with pytest.raises(ConfigError) as exc:
        load_config(_config(tmp_path, "[frontmatter]\nextension_fields = [1, 2]\n"))
    message = str(exc.value)
    assert "array of strings" in message or "must be quoted strings" in message


def test_reserved_words_must_be_a_list_of_strings(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config(_config(tmp_path, '[frontmatter]\nreserved_words = "acme"\n'))
    assert "reserved_words" in str(exc.value)
    assert "array of strings" in str(exc.value)


def test_frontmatter_section_must_be_a_table(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config(_config(tmp_path, 'frontmatter = "not a table"\n'))
    assert "frontmatter" in str(exc.value)
    assert "table" in str(exc.value)


def test_ignore_must_be_a_list_of_strings(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config(_config(tmp_path, 'ignore = "sizing"\n'))
    assert "ignore" in str(exc.value)
    assert "array of strings" in str(exc.value)


def test_malformed_toml_is_rejected_with_the_offending_line(tmp_path: Path) -> None:
    """Both parsers reject it; the wording differs because the parsers do.

    tomllib reports a syntax error and the loader wraps it with "Fix the TOML
    syntax"; the 3.10 fallback names the line and the key it could not read.
    """
    with pytest.raises(ConfigError) as exc:
        load_config(_config(tmp_path, "this is not = = toml\n"))
    message = str(exc.value)
    assert "Fix the TOML syntax" in message or "line 1" in message


# ---------------------------------------------------------------------------
# Valid configs still load
# ---------------------------------------------------------------------------


def test_reserved_words_round_trip(tmp_path: Path) -> None:
    config = load_config(_config(tmp_path, '[frontmatter]\nreserved_words = ["acme", "internal"]\n'))
    assert config.reserved_words == ("acme", "internal")


def test_ignore_round_trip(tmp_path: Path) -> None:
    config = load_config(_config(tmp_path, 'ignore = ["sizing", "compat.unverified"]\n'))
    assert config.ignore == ("sizing", "compat.unverified")


def test_no_config_path_yields_defaults() -> None:
    config = load_config(None)
    assert config.format is None
    assert config.extension_fields == frozenset()


# ---------------------------------------------------------------------------
# The 3.10 fallback parser, which has no tomllib to lean on
# ---------------------------------------------------------------------------


_needs_fallback = pytest.mark.skipif(
    sys.version_info >= (3, 11),
    reason="tomllib is stdlib from 3.11, so the fallback parser never runs",
)


@_needs_fallback
def test_fallback_parser_rejects_a_line_without_an_equals(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config(_config(tmp_path, "[frontmatter]\njust_a_key\n"))
    assert "missing '='" in str(exc.value)


@_needs_fallback
def test_fallback_parser_rejects_an_unterminated_section_header(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config(_config(tmp_path, "[frontmatter\nextension_fields = []\n"))
    assert "invalid section header" in str(exc.value)


@_needs_fallback
def test_fallback_parser_reads_booleans(tmp_path: Path) -> None:
    assert load_config(_config(tmp_path, "strict_all = true\n")).strict_all is True


@_needs_fallback
def test_fallback_parser_reads_integers(tmp_path: Path) -> None:
    assert load_config(_config(tmp_path, "max_lines = 250\n")).max_lines == 250


# ---------------------------------------------------------------------------
# Discovery stops where it should
# ---------------------------------------------------------------------------


def test_discovery_returns_none_when_nothing_is_found(tmp_path: Path) -> None:
    """A repo root with no config must not leak into a parent directory."""
    (tmp_path / ".git").mkdir()
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    assert find_config(skill_dir) is None


def test_discovery_accepts_a_file_anchor(tmp_path: Path) -> None:
    """find_config takes the scanned path, which is usually a file."""
    (tmp_path / ".git").mkdir()
    config = tmp_path / "skillcheck.toml"
    config.write_text("strict_all = true\n", encoding="utf-8")
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: demo\n---\n", encoding="utf-8")
    assert find_config(skill) == config


def test_discovery_prefers_the_nearest_config(tmp_path: Path) -> None:
    """An inner config shadows an outer one rather than merging with it."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "skillcheck.toml").write_text("max_lines = 100\n", encoding="utf-8")
    inner = tmp_path / "skills" / "demo"
    inner.mkdir(parents=True)
    nearest = inner / "skillcheck.toml"
    nearest.write_text("max_lines = 200\n", encoding="utf-8")
    assert find_config(inner) == nearest
    assert load_config(find_config(inner)).max_lines == 200
