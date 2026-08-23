#!/usr/bin/env python3
"""Capture the CLI's mode-conflict output for every pair of mode flags.

Writes tests/fixtures/mode_conflicts.json: for each unordered pair of mode
flags, the exit code and the exact stderr the CLI produced. The fixture is the
ground truth that tests/test_mode_conflicts.py replays, so the declarative
table in skillcheck.modes has to reproduce the pre-refactor wording byte for
byte rather than merely rejecting the same combinations.

Every pair is run against a path that does not exist. Conflict detection runs
before path resolution, so a conflicting pair exits on its conflict message and
a non-conflicting pair falls through to the same path error. That makes the
capture total: it records which pairs conflict as well as what they say.

Regenerate only when a conflict message is intentionally reworded, and read the
diff. A fixture that moves on its own means the CLI changed under you.
"""
from __future__ import annotations

import json
import subprocess
import sys
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "mode_conflicts.json"

# A path that cannot resolve, so non-conflicting pairs all land on one
# deterministic error instead of running validation and emitting real reports.
MISSING_PATH = "__does_not_exist__/SKILL.md"

# Flag to the argv fragment that activates it. Ingest flags take a value; the
# file is never opened because the conflict check runs first.
MODE_FLAGS: dict[str, list[str]] = {
    "--emit-critique-prompt": ["--emit-critique-prompt"],
    "--emit-graph": ["--emit-graph"],
    "--emit-graph-prompt": ["--emit-graph-prompt"],
    "--activation-hypotheses": ["--activation-hypotheses"],
    "--agent-reason": ["--agent-reason"],
    "--ingest-critique": ["--ingest-critique", "response.json"],
    "--ingest-graph": ["--ingest-graph", "response.json"],
    "--analyze-graph": ["--analyze-graph"],
    "--history": ["--history"],
    "--show-history": ["--show-history"],
}


def capture() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for flag_a, flag_b in combinations(sorted(MODE_FLAGS), 2):
        argv = [sys.executable, "-m", "skillcheck", MISSING_PATH]
        argv += MODE_FLAGS[flag_a] + MODE_FLAGS[flag_b]
        result = subprocess.run(argv, capture_output=True, text=True, cwd=REPO_ROOT)
        rows.append(
            {
                "flags": [flag_a, flag_b],
                "exit_code": result.returncode,
                "stderr": result.stderr,
            }
        )
    return rows


def main() -> int:
    rows = capture()
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    conflicts = sum(1 for r in rows if "Cannot use" in str(r["stderr"]))
    print(f"Wrote {FIXTURE.relative_to(REPO_ROOT)}: {len(rows)} pairs, {conflicts} conflicting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
