"""Direct coverage for is_template placeholder pattern matching.

The `[...]` branch of the bracketed-placeholder pattern was unescaped, so the
three dots matched any three characters. Bracketed acronyms like [ISO], [API],
and [CLI] in a real skill's description were misread as placeholders, which
silently suppressed deployment-blocking ERROR checks (directory-name match,
VS Code dirname, description scoring).
"""

from skillcheck.parser import parse
from skillcheck.template_detection import is_template
from tests.conftest import FIXTURES_DIR


def test_bracketed_acronyms_are_not_template():
    """[ISO]/[API]/[CLI] in a description must not read as placeholders."""
    skill = parse(FIXTURES_DIR / "non_template_bracket_acronym.md")
    assert is_template(skill) is False


def test_literal_ellipsis_placeholder_is_template():
    """A literal [...] placeholder must still be detected as a template."""
    skill = parse(FIXTURES_DIR / "template_bracket_placeholder.md")
    assert is_template(skill) is True
