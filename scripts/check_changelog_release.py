#!/usr/bin/env python3
"""Assert CHANGELOG.md is in a releasable state for a given version.

Run by release.yml before anything is published, and importable by
tests/test_changelog_release_check.py so the invariant is covered by the suite
rather than only by a workflow that runs on tag pushes.

The release flow expects entries to accumulate under [Unreleased] and to be
promoted to a version heading by release-notes.yml after the GitHub release is
published. v1.4.1 broke that: the release commit hand-promoted part of the
block, so the [1.4.1] heading already existed when the workflow ran. The
promotion step treats an existing heading as "already done" and no-ops, so the
nine entries still sitting under [Unreleased] shipped in 1.4.1 without ever
appearing in its release notes.

Two states are rejected for a version being tagged:

1. A [X.Y.Z] heading exists and [Unreleased] is not empty. Whatever is left
   under [Unreleased] is about to ship unrecorded.
2. No [X.Y.Z] heading and [Unreleased] is empty. There is nothing to promote,
   so the release would ship with no notes at all.

Usage: check_changelog_release.py 1.4.2 [path/to/CHANGELOG.md]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

_UNRELEASED = re.compile(r"^##\s*\[Unreleased\]\s*$", re.MULTILINE)
_ANY_HEADING = re.compile(r"^##\s*\[", re.MULTILINE)


def unreleased_body(text: str) -> str:
    """Return the [Unreleased] section body, stripped. Empty if absent."""
    match = _UNRELEASED.search(text)
    if not match:
        return ""
    start = match.end()
    following = _ANY_HEADING.search(text, start)
    end = following.start() if following else len(text)
    return text[start:end].strip()


def has_version_heading(text: str, version: str) -> bool:
    """Whether a '## [version]' heading is already present."""
    return re.search(rf"^##\s*\[{re.escape(version)}\]", text, re.MULTILINE) is not None


def check(text: str, version: str) -> list[str]:
    """Return the reasons this CHANGELOG cannot release `version`. Empty means OK."""
    body = unreleased_body(text)
    promoted = has_version_heading(text, version)
    problems = []

    if promoted and body:
        problems.append(
            f"CHANGELOG.md already has a [{version}] heading and [Unreleased] is not empty. "
            f"release-notes.yml skips promotion when the heading exists, so these entries would "
            f"ship in {version} without appearing in its notes. Move them under [{version}] "
            f"or hold them back for the next version:\n"
            + "\n".join(f"    {line}" for line in body.splitlines() if line.strip())
        )
    if not promoted and not body:
        problems.append(
            f"CHANGELOG.md has no [{version}] heading and an empty [Unreleased] section, "
            f"so {version} would be released with no notes. Record the changes before tagging."
        )
    return problems


def main(argv: list[str]) -> int:
    if not 2 <= len(argv) <= 3:
        print(f"usage: {Path(argv[0]).name} VERSION [CHANGELOG_PATH]", file=sys.stderr)
        return 2

    version = argv[1].lstrip("v")
    path = Path(argv[2]) if len(argv) == 3 else CHANGELOG

    problems = check(path.read_text(encoding="utf-8"), version)
    if problems:
        for problem in problems:
            print(f"{path.name}: {problem}", file=sys.stderr)
        return 1

    print(f"{path.name} is ready to release {version}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
