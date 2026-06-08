import importlib.util
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
