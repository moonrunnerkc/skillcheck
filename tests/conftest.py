import importlib.util
import os
import sys
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Invoke the CLI through the same interpreter that runs the tests, rather than a
# bare ``skillcheck`` entry on PATH. PATH may resolve to a stale console script
# built for a different Python (e.g. a system 3.9 install that cannot import the
# 3.10+ source), which is non-hermetic and masks the package under test.
SKILLCHECK_CMD = [sys.executable, "-m", "skillcheck"]

# CLI tests are skipped when the package is not importable in this interpreter.
CLI_AVAILABLE = importlib.util.find_spec("skillcheck") is not None


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


def pytest_configure(config: pytest.Config) -> None:
    """Make coverage follow the CLI subprocesses.

    Most CLI tests shell out to ``python -m skillcheck`` on purpose: exit codes
    and stdout are the contract, and only a real process exercises them. The
    tracer does not follow a subprocess by default, so cli.py and commands.py
    measured near zero despite being the most exercised code in the suite.

    Coverage ships a .pth hook that calls ``coverage.process_startup()`` when
    COVERAGE_PROCESS_START is set, so pointing it at pyproject.toml is enough
    for the child to start measuring before it imports skillcheck. Combining the
    per-process data files is pytest-cov's job, given ``parallel = true``.

    Skipped when the run has no coverage active (``--no-cov``), where starting
    coverage in every subprocess would be pure overhead.
    """
    if not getattr(config.option, "cov_source", None):
        return
    os.environ["COVERAGE_PROCESS_START"] = str(Path(__file__).parent.parent / "pyproject.toml")
