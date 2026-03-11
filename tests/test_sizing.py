import pytest

from skillcheck.parser import parse
from skillcheck.result import Severity
from skillcheck.rules.sizing import make_line_count_rule, make_token_estimate_rule
from skillcheck.tokenizer import estimate_tokens
from tests.conftest import FIXTURES_DIR


# ---------------------------------------------------------------------------
# sizing.body.line-count
# ---------------------------------------------------------------------------

def test_line_count_warns_for_long_body():
    skill = parse(FIXTURES_DIR / "bad_body_long.md")
    rule = make_line_count_rule(max_lines=500)
    diagnostics = rule(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "sizing.body.line-count"
    assert diagnostics[0].severity == Severity.WARNING
    assert "500" in diagnostics[0].message


def test_line_count_passes_for_short_body():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    rule = make_line_count_rule(max_lines=500)
    assert rule(skill) == []


def test_line_count_respects_custom_threshold():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    # Force a violation by setting an unrealistically low threshold.
    rule = make_line_count_rule(max_lines=1)
    diagnostics = rule(skill)
    assert len(diagnostics) == 1
    assert "1" in diagnostics[0].message


def test_line_count_passes_at_exact_threshold(tmp_path):
    # Build a file with exactly 10 lines total (including frontmatter).
    lines = ["---", "name: edge-skill", "description: Edge case skill.", "---"]
    lines += ["body line"] * 6  # 4 + 6 = 10 total
    content = "\n".join(lines) + "\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content)
    skill = parse(f)
    rule = make_line_count_rule(max_lines=10)
    assert rule(skill) == []


# ---------------------------------------------------------------------------
# sizing.body.token-estimate
# ---------------------------------------------------------------------------

def test_token_estimate_warns_when_exceeded():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    rule = make_token_estimate_rule(max_tokens=1)
    diagnostics = rule(skill)
    assert len(diagnostics) == 1
    assert diagnostics[0].rule == "sizing.body.token-estimate"
    assert diagnostics[0].severity == Severity.WARNING


def test_token_estimate_passes_for_normal_file():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    rule = make_token_estimate_rule(max_tokens=8000)
    assert rule(skill) == []


def test_token_estimate_is_positive():
    skill = parse(FIXTURES_DIR / "valid_basic.md")
    count = estimate_tokens(skill.raw_text)
    assert count > 0


def test_token_estimate_grows_with_content():
    short_text = "Hello world."
    long_text = "Hello world. " * 100
    assert estimate_tokens(long_text) > estimate_tokens(short_text)


def test_token_estimate_counts_punctuation_runs():
    # A file full of YAML punctuation (colons, hyphens, pipes) should not
    # estimate as zero: each punct run contributes ~1.5 tokens.
    structured = "---\nname: a\ntags:\n  - x\n  - y\n---\n"
    assert estimate_tokens(structured) > 5


def test_token_estimate_within_reasonable_bound():
    # For typical English prose, the estimate should be within 30% of a
    # word-count-based reference (each word ~1 token for common English).
    text = "Generates commit messages from staged diffs using conventional commit format."
    word_count = len(text.split())
    estimate = estimate_tokens(text)
    # Allow up to 2x word count (subword splits) and floor of word count * 0.8.
    assert word_count * 0.8 <= estimate <= word_count * 2
