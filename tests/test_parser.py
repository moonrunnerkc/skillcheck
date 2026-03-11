from pathlib import Path

import pytest

from skillcheck.parser import ParseError, ParsedSkill, parse
from tests.conftest import FIXTURES_DIR


def test_parses_valid_frontmatter():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert skill.frontmatter["name"] == "pdf-processor"
    assert "description" in skill.frontmatter


def test_parses_body_content():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert "basic skill" in skill.body


def test_body_does_not_contain_frontmatter_delimiters():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert not skill.body.startswith("---")


def test_raw_text_contains_full_file():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert skill.raw_text.startswith("---")
    assert "pdf-processor" in skill.raw_text
    assert "basic skill" in skill.raw_text


def test_body_lines_counts_only_body():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    # Body is after frontmatter; line count must be positive and less than raw line count.
    assert skill.body_lines > 0
    assert skill.body_lines < len(skill.raw_text.splitlines())


def test_handles_missing_frontmatter():
    skill = parse(FIXTURES_DIR / "bad_no_frontmatter.md")
    assert skill.frontmatter == {}
    assert "no frontmatter" in skill.body.lower() or len(skill.body) > 0


def test_handles_file_with_all_known_fields():
    skill = parse(FIXTURES_DIR / "valid_full.md")
    assert skill.frontmatter["name"] == "document-analyzer"
    assert skill.frontmatter["version"] == "1.0.0"
    assert "tags" in skill.frontmatter


def test_path_is_preserved():
    path = FIXTURES_DIR / "valid_basic.md"
    skill = parse(path)
    assert skill.path == path


def test_raises_parse_error_for_non_utf8(tmp_path):
    bad_file = tmp_path / "SKILL.md"
    # Write bytes that are not valid UTF-8 (not valid as utf-8-sig either)
    bad_file.write_bytes(b"---\nname: \xff\xfe\x00\x01\n---\n")
    with pytest.raises(ParseError, match="not valid UTF-8"):
        parse(bad_file)


def test_handles_bom_prefixed_file(tmp_path):
    skill_file = tmp_path / "SKILL.md"
    # BOM + valid UTF-8 YAML frontmatter
    content = "\ufeff---\nname: bom-skill\ndescription: A skill prefixed with a BOM.\n---\nBody.\n"
    skill_file.write_bytes(content.encode("utf-8"))
    skill = parse(skill_file)
    assert skill.frontmatter["name"] == "bom-skill"
