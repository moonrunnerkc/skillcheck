"""One guard for every file skillcheck reads from disk.

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

The size cap alone was not enough. An audit of the same four paths found that a
ledger or a skillcheck.toml holding non-UTF-8 bytes raised UnicodeDecodeError
straight out of `read_text`, printing a traceback and exiting 1. The config case
is the worse of the two, because `find_config` discovers skillcheck.toml by
walking up from the scanned path: a poisoned file sitting next to a skill
crashed any scan of that tree, with no flag involved. `read_guarded_text` now
checks size, then UTF-8 validity, then control characters, all before a YAML or
JSON parser sees the content.

The guards take the caller's exception type instead of raising one of their own.
Each reader already has a typed error with remediation text its tests pin
(LedgerError says how to reset a corrupt ledger, ParseError names the path), and
a shared guard should add the checks without flattening those messages into one
generic failure.
"""

from __future__ import annotations

import re
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
            f"{what} at {display_path(path)} is {size} bytes, over the {max_bytes}-byte "
            f"limit. skillcheck refuses to load it. Split the file or reduce its size."
        )


class UntrustedInputError(Exception):
    """A file failed the untrusted-input policy before it could be parsed."""


# C0 controls other than tab, newline, and carriage return, plus DEL. A NUL or a
# raw ESC in a ledger or a config is either a binary file handed to a text
# parser or an attempt to smuggle terminal escapes through a diagnostic. Neither
# has a legitimate reading, so the file is refused rather than repaired.
#
# C1 (0x80-0x9F) is deliberately not rejected: those are ordinary code points in
# valid UTF-8 text, and the ones that matter are already neutralized for display
# by agents._ingest.sanitize_ingested_text. Rejecting them here would refuse
# legitimate content to solve a problem that is already solved downstream.
_FORBIDDEN_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def display_path(path: Path) -> str:
    """Render *path* for a diagnostic without leaking the host's directory layout.

    Relative to the working directory when the file is under it, otherwise the
    bare file name. CI logs and shared reports quote these messages verbatim, so
    an absolute path publishes the build machine's layout for no benefit; the
    same reasoning applied to reference paths in 1.4.1.

    A file outside the working directory deliberately does not get a ``../..``
    chain. Walking up out of the tree spells the absolute layout a segment at a
    time, which is the thing being avoided, and tells the reader nothing they
    can act on. The name alone is enough to identify which file was refused.
    """
    try:
        resolved = path.resolve()
        cwd = Path.cwd().resolve()
    except OSError:
        return path.name
    try:
        return resolved.relative_to(cwd).as_posix()
    except ValueError:
        # Not under the working directory, or a different drive on Windows.
        return path.name


def read_guarded_text(
    path: Path,
    *,
    max_bytes: int,
    what: str,
    error_cls: type[Exception] = UntrustedInputError,
) -> str:
    """Read *path* as text after checking it against the untrusted-input policy.

    Three checks, all before any YAML or JSON parser sees the content, because a
    parser handed a gigabyte of binary is the thing being guarded against:

    1. Size, measured with stat so an oversized file is never read.
    2. UTF-8 validity, decoded explicitly rather than relying on the reader.
    3. Control characters, which mark a binary file or an escape-smuggling
       attempt.

    Args:
        path: File to read. Callers check existence themselves.
        max_bytes: Inclusive size ceiling.
        what: Noun for the message, e.g. "Ledger" or "Config".
        error_cls: Exception type for policy failures, so each caller keeps its
            own type and remediation wording.

    Returns:
        The decoded text.

    Raises:
        error_cls: On any policy failure.
        OSError: Propagated unchanged. Callers already wrap read failures with
            their own permission-specific message, and those messages are pinned
            by their tests.
    """
    enforce_size_cap(path, max_bytes, error_cls, what)
    raw = path.read_bytes()
    shown = display_path(path)

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise error_cls(
            f"{what} at {shown} is not valid UTF-8: byte 0x{raw[exc.start]:02x} at offset "
            f"{exc.start} is not decodable. The file may be binary or saved in another "
            f"encoding. Re-save it as UTF-8."
        ) from exc

    reject_control_characters(text, what=what, source=shown, error_cls=error_cls)
    return text


def reject_control_characters(
    text: str,
    *,
    what: str,
    source: str,
    error_cls: type[Exception] = UntrustedInputError,
) -> None:
    """Raise *error_cls* if *text* carries a control character the policy refuses.

    Split out from read_guarded_text so stdin, which arrives already decoded and
    has no size to stat, gets the same policy as a file.
    """
    found = _FORBIDDEN_CONTROL_RE.search(text)
    if found is not None:
        raise error_cls(
            f"{what} at {source} contains the control character 0x{ord(found.group()):02x} "
            f"at offset {found.start()}. Control characters other than tab, newline, and "
            f"carriage return are refused before parsing. The file may be binary or corrupt."
        )
