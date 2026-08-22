"""Size caps for every file skillcheck reads from disk.

skillcheck reads four kinds of file, and until now only one of them was
bounded. `--ingest-critique` and `--ingest-graph` checked their payload against
MAX_INGEST_BYTES because an agent response is obviously untrusted, while the
SKILL.md itself, the `.skillcheck-history.json` ledger, and `skillcheck.toml`
were read with a bare `path.read_text()`. Those three are just as attacker
influenced in the case that matters: CI running skillcheck over a pull request
from a fork, where every one of them arrives from the branch under test. A
multi-gigabyte SKILL.md is read fully into memory before the first rule runs.

The caps differ because the files do. A SKILL.md that honors the disclosure
budgets is a few KB, a ledger grows one entry per run, and a config is tiny.
Each is set generously enough that no legitimate file is refused.

`enforce_size_cap` deliberately takes the caller's exception type instead of
raising one of its own. Each reader already has a typed error with remediation
text its tests pin (LedgerError says how to reset a corrupt ledger, ParseError
names the path), and a shared guard should add the bound without flattening
those messages into one generic failure.
"""

from __future__ import annotations

from pathlib import Path

# A SKILL.md that respects the agentskills.io disclosure budgets is a few KB.
# The default thresholds are 500 lines and 8000 tokens, so 4 MiB is roughly
# three orders of magnitude of headroom over anything meant to pass.
MAX_SKILL_BYTES = 4 * 1024 * 1024

# A ledger gains one entry per `--history` run. At a few hundred bytes an entry,
# 8 MiB is tens of thousands of runs.
MAX_LEDGER_BYTES = 8 * 1024 * 1024

# skillcheck.toml holds a handful of scalar defaults and an extension-field list.
MAX_CONFIG_BYTES = 1 * 1024 * 1024

# A critique or graph response is a few KB. Re-exported by agents._ingest,
# which enforces it against both stdin and a response file.
MAX_INGEST_BYTES = 5 * 1024 * 1024


def enforce_size_cap(
    path: Path,
    max_bytes: int,
    error_cls: type[Exception],
    what: str,
) -> None:
    """Raise *error_cls* when *path* is larger than *max_bytes*.

    Checked with `stat` before any read, so an oversized file is refused
    without being pulled into memory first.

    Args:
        path: File to measure. Must exist; callers handle absence themselves.
        max_bytes: Inclusive ceiling. A file of exactly this size is accepted.
        error_cls: Exception type to raise, so each reader keeps its own type.
        what: Noun for the message, e.g. "SKILL.md" or "ledger".

    Raises:
        error_cls: If the file is larger than the cap.
    """
    try:
        size = path.stat().st_size
    except OSError:
        # Unreadable for a reason the caller's own read will surface with its
        # established message. Do not pre-empt it with a size error.
        return
    if size > max_bytes:
        raise error_cls(
            f"{what} at {path} is {size} bytes, over the {max_bytes}-byte limit. "
            f"skillcheck refuses to load it. Split the file or reduce its size."
        )
