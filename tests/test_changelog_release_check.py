"""Guards the release-readiness check for CHANGELOG.md.

The regression this encodes is real: v1.4.1 was tagged with a hand-written
[1.4.1] heading and nine entries still under [Unreleased]. release-notes.yml
skips promotion when the version heading already exists, so those nine entries
shipped in 1.4.1 and never reached its release notes. `check` is what
release.yml runs before it publishes anything.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).parents[1]

HEADER = """# Changelog

All notable changes to this project will be documented in this file.

"""


def load_checker() -> ModuleType:
    path = REPO_ROOT / "scripts" / "check_changelog_release.py"
    spec = importlib.util.spec_from_file_location("check_changelog_release", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_promoted_version_with_empty_unreleased_passes() -> None:
    text = HEADER + "## [Unreleased]\n\n## [1.4.2] - 2026-08-22\n\n### Fixed\n\n- A fix.\n"
    assert load_checker().check(text, "1.4.2") == []


def test_unpromoted_entries_with_no_version_heading_pass() -> None:
    """The normal flow: entries wait under [Unreleased] for the workflow to promote."""
    text = HEADER + "## [Unreleased]\n\n### Fixed\n\n- A fix.\n\n## [1.4.1] - 2026-07-09\n\n- Older.\n"
    assert load_checker().check(text, "1.4.2") == []


def test_version_heading_plus_leftover_unreleased_entries_fail() -> None:
    """The v1.4.1 regression: a partial hand promotion strands the remainder."""
    text = (
        HEADER
        + "## [Unreleased]\n\n### Fixed\n\n- Stranded entry.\n\n"
        + "## [1.4.2] - 2026-08-22\n\n### Added\n\n- Promoted entry.\n"
    )
    problems = load_checker().check(text, "1.4.2")
    assert len(problems) == 1
    assert "would ship in 1.4.2" in problems[0]
    assert "Stranded entry" in problems[0]


def test_no_version_heading_and_empty_unreleased_fails() -> None:
    text = HEADER + "## [Unreleased]\n\n## [1.4.1] - 2026-07-09\n\n- Older.\n"
    problems = load_checker().check(text, "1.4.2")
    assert len(problems) == 1
    assert "no notes" in problems[0]


def test_missing_unreleased_section_is_treated_as_empty() -> None:
    text = HEADER + "## [1.4.2] - 2026-08-22\n\n### Added\n\n- Promoted entry.\n"
    assert load_checker().check(text, "1.4.2") == []


def test_heading_match_is_exact_not_prefix() -> None:
    """A [1.4.10] heading must not satisfy a 1.4.1 release."""
    text = HEADER + "## [Unreleased]\n\n### Fixed\n\n- Pending.\n\n## [1.4.10] - 2026-08-22\n\n- Other.\n"
    assert load_checker().check(text, "1.4.1") == []


def test_main_rejects_a_version_that_is_not_a_version(tmp_path: Path) -> None:
    """An unset or malformed tag name must not pass the gate silently.

    An empty version matches no heading, which leaves a filling [Unreleased]
    looking like the normal between-releases state, so `check` alone would
    report the CHANGELOG as ready.
    """
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(HEADER + "## [Unreleased]\n\n### Added\n\n- Pending.\n", encoding="utf-8")
    main = load_checker().main

    assert main(["check", "", str(changelog)]) == 2
    assert main(["check", "not-a-version", str(changelog)]) == 2
    assert main(["check", "v1.5.0", str(changelog)]) == 0


def test_released_version_with_pending_next_entries_passes() -> None:
    """Normal development after a release: entries pile up for the next version.

    The check is asked about the version being tagged, never the version already
    shipped, so a [1.4.1] heading beside a filling [Unreleased] is expected here.
    """
    text = HEADER + "## [Unreleased]\n\n### Added\n\n- Next thing.\n\n## [1.4.1] - 2026-07-09\n\n- Shipped.\n"
    assert load_checker().check(text, "1.5.0") == []
