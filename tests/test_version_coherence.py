"""Release coherence: pyproject.toml, __init__.__version__, CHANGELOG, and
self-host SKILL.md frontmatter must all agree on the current version."""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent


def _pyproject_version() -> str:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    # Match only inside the [project] section to avoid false positives from
    # [tool.*] sections that also use a version key.
    project_block = re.search(
        r"\[project\](.*?)(?=^\[|\Z)", text, re.DOTALL | re.MULTILINE
    )
    assert project_block, "pyproject.toml has no [project] section"
    match = re.search(r'^version\s*=\s*"([^"]+)"', project_block.group(1), re.MULTILINE)
    assert match, "pyproject.toml [project] section has no version field"
    return match.group(1)


def _init_version() -> str:
    text = (REPO_ROOT / "src" / "skillcheck" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "src/skillcheck/__init__.py has no __version__ assignment"
    return match.group(1)


def _changelog_top_release() -> str:
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        match = re.match(r"^##\s+\[(\d+\.\d+\.\d+)\]", line)
        if match:
            return match.group(1)
    raise AssertionError("CHANGELOG.md has no versioned ## [X.Y.Z] heading")


def _self_host_skill_version() -> str:
    text = (REPO_ROOT / "skills" / "skillcheck" / "SKILL.md").read_text(encoding="utf-8")
    # Strip the leading "---\n" and find the closing "---"
    if not text.startswith("---"):
        raise AssertionError("skills/skillcheck/SKILL.md has no frontmatter delimiter")
    inner = text[3:]
    end = inner.index("\n---")
    fm = yaml.safe_load(inner[:end])
    assert "version" in fm, "skills/skillcheck/SKILL.md frontmatter has no version field"
    return str(fm["version"])


def test_pyproject_and_init_versions_match():
    pyproject = _pyproject_version()
    init = _init_version()
    assert pyproject == init, (
        f"Version mismatch: pyproject.toml has {pyproject!r}, "
        f"src/skillcheck/__init__.py has {init!r}"
    )


def test_changelog_top_release_matches_init():
    changelog = _changelog_top_release()
    init = _init_version()
    assert changelog == init, (
        f"Version mismatch: CHANGELOG.md top release is {changelog!r}, "
        f"src/skillcheck/__init__.py has {init!r}"
    )


def test_self_host_skill_version_matches():
    skill = _self_host_skill_version()
    init = _init_version()
    assert skill == init, (
        f"Version mismatch: skills/skillcheck/SKILL.md frontmatter has {skill!r}, "
        f"src/skillcheck/__init__.py has {init!r}"
    )
