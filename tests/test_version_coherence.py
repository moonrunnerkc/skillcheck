"""Release coherence: pyproject.toml, __init__.__version__, CHANGELOG, and
self-host SKILL.md frontmatter must all agree on the current version.

Also pins the self-host skill to a single path. A second copy at the repo root
went unmaintained from v1.3.0 to v1.4.1 and drifted to a stale version and a
weaker description while nothing in CI could see it, because every check here
and in the Makefile reads skills/skillcheck/SKILL.md."""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
SELF_HOST_SKILL = Path("skills/skillcheck/SKILL.md")


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


def _tracked_skill_files() -> list[Path]:
    """Every tracked SKILL.md outside tests/fixtures, as repo-relative paths."""
    result = subprocess.run(
        ["git", "ls-files", "*SKILL.md", "SKILL.md"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("not a git checkout; cannot enumerate tracked files")
    paths = [Path(line) for line in result.stdout.split() if line]
    return [p for p in paths if "fixtures" not in p.parts]


def test_only_one_self_host_skill_is_tracked():
    """One skill definition, so there is nothing to drift against.

    The version, description, and body checks above all read
    skills/skillcheck/SKILL.md. Any other SKILL.md in the tree is unguarded by
    them, which is how the former root copy fell two versions behind.
    """
    found = _tracked_skill_files()
    assert found == [SELF_HOST_SKILL], (
        f"Expected exactly one tracked SKILL.md at {SELF_HOST_SKILL}, found "
        f"{[str(p) for p in found]}. A second copy is not covered by the coherence "
        f"checks in this module and will drift."
    )
