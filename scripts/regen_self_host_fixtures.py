#!/usr/bin/env python3
"""Regenerate tests/fixtures/self_host/graph_clean.json from the live skill.

Runs 'skillcheck skills/skillcheck/SKILL.md --emit-graph --format json', strips
the 'source' field (which the heuristic emits as "heuristic" but the agent-mode
schema accepts as "agent"), and writes the result to the fixture path.

critique_clean.json is NOT regenerated here: those scores are hand-picked.
An agent's actual response would vary. Edit that file manually if needed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "skillcheck" / "SKILL.md"
GRAPH_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "self_host" / "graph_clean.json"


def main() -> None:
    """Emit the heuristic graph, strip 'source', write the fixture."""
    result = subprocess.run(
        [sys.executable, "-m", "skillcheck", str(SKILL_PATH), "--emit-graph", "--format", "json"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        print(f"skillcheck exited {result.returncode}:", file=sys.stderr)
        print(result.stderr or result.stdout, file=sys.stderr)
        sys.exit(1)

    data = json.loads(result.stdout)
    data.pop("source", None)  # strip heuristic/agent label; parser accepts any valid graph

    GRAPH_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_FIXTURE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {GRAPH_FIXTURE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
