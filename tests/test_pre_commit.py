"""End-to-end pre-commit hook tests."""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from tests.conftest import FIXTURES_DIR

pytestmark = pytest.mark.skipif(
    shutil.which("pre-commit") is None,
    reason="pre-commit not installed",
)


def _make_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with a pre-commit config pointing at local skillcheck."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True)

    # Use local repo type so pre-commit resolves the hook from the installed package
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        textwrap.dedent("""\
        repos:
          - repo: local
            hooks:
              - id: skillcheck
                name: skillcheck
                entry: skillcheck
                language: python
                files: '(^|/)SKILL\\.md$'
                pass_filenames: true
                args: [--skip-dirname-check]
        """),
        encoding="utf-8",
    )
    return tmp_path


def _commit_skill(tmp_path: Path, skill_src: Path, dest_dir: str = "skill") -> None:
    """Copy a SKILL.md fixture into the repo, add, and commit."""
    skill_dir = tmp_path / dest_dir
    skill_dir.mkdir(exist_ok=True)
    shutil.copy(skill_src, skill_dir / "SKILL.md")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"add {dest_dir}"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )


def test_pre_commit_pass(tmp_path: Path) -> None:
    """A clean SKILL.md passes the pre-commit hook."""
    repo = _make_repo(tmp_path)
    _commit_skill(repo, FIXTURES_DIR / "valid_basic.md", dest_dir="valid-skill")

    result = subprocess.run(
        ["pre-commit", "run", "skillcheck", "--all-files"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_pre_commit_fail(tmp_path: Path) -> None:
    """A SKILL.md with known violations fails the pre-commit hook."""
    repo = _make_repo(tmp_path)
    _commit_skill(repo, FIXTURES_DIR / "bad_name_caps.md", dest_dir="broken-skill")

    result = subprocess.run(
        ["pre-commit", "run", "skillcheck", "--all-files"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1