import pytest

from skillcheck.parser import parse
from skillcheck.result import Severity
from skillcheck.rules.frontmatter import (
    check_description_max_length,
    check_description_no_xml_tags,
    check_description_non_empty,
    check_description_person_voice,
    check_description_required,
    check_name_charset,
    check_name_max_length,
    check_name_required,
    check_name_reserved_words,
    check_unknown_fields,
)
from tests.conftest import FIXTURES_DIR


# ---------------------------------------------------------------------------
# name.required
# ---------------------------------------------------------------------------

def test_name_required_fires_when_missing():
    skill = parse(FIXTURES_DIR / "bad_no_frontmatter.md")
    diagnostics = check_name_required(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.name.required"
    assert diagnostics[0].severity == Severity.ERROR


def test_name_required_passes_for_valid_file():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert check_name_required(skill) == []


# ---------------------------------------------------------------------------
# name.max-length
# ---------------------------------------------------------------------------

def test_name_rejects_long_name():
    skill = parse(FIXTURES_DIR / "bad_name_long.md")
    diagnostics = check_name_max_length(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.name.max-length"
    assert diagnostics[0].severity == Severity.ERROR
    assert "64" in diagnostics[0].message


def test_name_accepts_name_at_length_boundary(tmp_path):
    name_64 = "a" * 64
    content = f"---\nname: {name_64}\ndescription: Boundary test.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    assert check_name_max_length(skill) == []


def test_name_rejects_name_one_over_boundary(tmp_path):
    name_65 = "a" * 65
    content = f"---\nname: {name_65}\ndescription: Over boundary test.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_name_max_length(skill)
    assert len(diagnostics) == 1
    assert "65" in diagnostics[0].message


# ---------------------------------------------------------------------------
# name.invalid-chars
# ---------------------------------------------------------------------------

def test_name_rejects_uppercase():
    skill = parse(FIXTURES_DIR / "bad_name_caps.md")
    diagnostics = check_name_charset(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.name.invalid-chars"
    assert diagnostics[0].severity == Severity.ERROR
    assert "PDF-Processing" in diagnostics[0].message


def test_name_accepts_lowercase_with_hyphens():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert check_name_charset(skill) == []


def test_name_accepts_lowercase_with_numbers(tmp_path):
    content = "---\nname: skill-v2\ndescription: Version 2 skill.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    assert check_name_charset(skill) == []


def test_name_rejects_spaces(tmp_path):
    content = "---\nname: my skill\ndescription: Has a space.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_name_charset(skill)
    assert len(diagnostics) == 1
    assert "invalid-chars" in diagnostics[0].rule


# ---------------------------------------------------------------------------
# name.reserved-word
# ---------------------------------------------------------------------------

def test_name_rejects_reserved_word_claude():
    skill = parse(FIXTURES_DIR / "bad_name_reserved.md")
    diagnostics = check_name_reserved_words(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.name.reserved-word"
    assert "claude" in diagnostics[0].message


def test_name_rejects_reserved_word_anthropic(tmp_path):
    content = "---\nname: anthropic-helper\ndescription: Uses a reserved word.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_name_reserved_words(skill)
    assert len(diagnostics) == 1
    assert "anthropic" in diagnostics[0].message


def test_name_accepts_unreserved_name():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert check_name_reserved_words(skill) == []


# ---------------------------------------------------------------------------
# description.required
# ---------------------------------------------------------------------------

def test_description_required_fires_when_missing():
    skill = parse(FIXTURES_DIR / "bad_no_frontmatter.md")
    diagnostics = check_description_required(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.description.required"
    assert diagnostics[0].severity == Severity.ERROR


def test_description_required_passes_for_valid_file():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert check_description_required(skill) == []


# ---------------------------------------------------------------------------
# description.empty
# ---------------------------------------------------------------------------

def test_description_rejects_empty():
    skill = parse(FIXTURES_DIR / "bad_desc_empty.md")
    diagnostics = check_description_non_empty(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.description.empty"
    assert diagnostics[0].severity == Severity.ERROR


def test_description_accepts_non_empty():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert check_description_non_empty(skill) == []


# ---------------------------------------------------------------------------
# description.max-length
# ---------------------------------------------------------------------------

def test_description_rejects_over_1024_chars(tmp_path):
    long_desc = "A" * 1025
    content = f"---\nname: my-skill\ndescription: {long_desc}\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_description_max_length(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.description.max-length"
    assert "1024" in diagnostics[0].message


def test_description_accepts_exactly_1024_chars(tmp_path):
    exact_desc = "B" * 1024
    content = f"---\nname: my-skill\ndescription: {exact_desc}\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    assert check_description_max_length(skill) == []


# ---------------------------------------------------------------------------
# description.xml-tags
# ---------------------------------------------------------------------------

def test_description_rejects_xml_tags(tmp_path):
    content = "---\nname: my-skill\ndescription: Processes <file> inputs.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_description_no_xml_tags(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.description.xml-tags"


def test_description_accepts_no_xml_tags():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert check_description_no_xml_tags(skill) == []


# ---------------------------------------------------------------------------
# description.person-voice
# ---------------------------------------------------------------------------

def test_description_rejects_first_person():
    skill = parse(FIXTURES_DIR / "bad_desc_person.md")
    diagnostics = check_description_person_voice(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.description.person-voice"
    assert diagnostics[0].severity == Severity.ERROR


def test_description_rejects_second_person(tmp_path):
    content = "---\nname: my-skill\ndescription: You can use this to generate reports.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_description_person_voice(skill)
    assert len(diagnostics) == 1
    assert "second-person" in diagnostics[0].message


def test_description_accepts_third_person():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    assert check_description_person_voice(skill) == []


def test_description_accepts_third_person_with_verbs(tmp_path):
    content = "---\nname: my-skill\ndescription: Generates structured reports from raw data.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    assert check_description_person_voice(skill) == []


# ---------------------------------------------------------------------------
# frontmatter.field.unknown
# ---------------------------------------------------------------------------

def test_unknown_field_triggers_warning():
    skill = parse(FIXTURES_DIR / "bad_field_typo.md")
    diagnostics = check_unknown_fields(skill)
    rules = [d.rule for d in diagnostics]
    assert "frontmatter.field.unknown" in rules
    severities = [d.severity for d in diagnostics if d.rule == "frontmatter.field.unknown"]
    assert all(s == Severity.WARNING for s in severities)
    messages = " ".join(d.message for d in diagnostics)
    assert "auther" in messages


def test_known_fields_produce_no_warning():
    skill = parse(FIXTURES_DIR / "valid_full.md")
    diagnostics = check_unknown_fields(skill)
    assert diagnostics == []


# ---------------------------------------------------------------------------
# Regression: _field_line must not match body content
# ---------------------------------------------------------------------------

def test_field_line_does_not_match_body_content(tmp_path):
    # The body has 'name: something' but frontmatter does not have name.
    # Line number reported should be None, not the body line.
    content = "---\ndescription: Analyzes data from input sources.\n---\n\nname: something in the body\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_name_required(skill)
    assert len(diagnostics) == 1
    # No line number should be reported since name is absent from frontmatter.
    assert diagnostics[0].line is None


def test_field_line_reports_correct_frontmatter_line(tmp_path):
    content = "---\nname: my-skill\ndescription: Analyzes things.\n---\nname: body content\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    # name is on line 2; body 'name:' on line 5 must NOT be reported.
    from skillcheck.rules.frontmatter import _field_line
    assert _field_line(skill.raw_text, "name") == 2


# ---------------------------------------------------------------------------
# Regression: first-person possessive "My" must be caught
# ---------------------------------------------------------------------------

def test_description_rejects_first_person_possessive(tmp_path):
    content = "---\nname: my-skill\ndescription: My approach analyzes documents efficiently.\n---\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    diagnostics = check_description_person_voice(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "frontmatter.description.person-voice"
