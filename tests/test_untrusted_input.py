"""Every user-controlled file goes through one guard before a parser sees it.

The audit that prompted this found two uncaught crashes. A ledger or a
skillcheck.toml containing non-UTF-8 bytes raised UnicodeDecodeError straight
out of `path.read_text`, printing a traceback and exiting 1. The config case is
the worse of the two: `find_config` discovers skillcheck.toml by walking up from
the scanned path, so a poisoned file sitting next to a skill crashed skillcheck
for anyone who scanned that tree, with no flag involved.

`read_guarded_text` now checks size, UTF-8 validity, and control characters, in
that order, before any YAML or JSON parser runs. Size is checked with stat so an
oversized file is never read into memory at all.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from skillcheck.config_loader import ConfigError, load_config
from skillcheck.core.history import LedgerError
from skillcheck.core.history_io import load_ledger
from skillcheck.io_limits import (
    MAX_CONFIG_BYTES,
    MAX_LEDGER_BYTES,
    UntrustedInputError,
    display_path,
    read_guarded_text,
    reject_control_characters,
)
from tests.conftest import SKILLCHECK_CMD

REPO_ROOT = Path(__file__).parents[1]

VALID_SKILL = "---\nname: {name}\ndescription: Validates guarded reads when scanning a skill.\n---\n\nBody.\n"


def _skill(directory: Path, name: str = "guarded") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "SKILL.md"
    path.write_text(VALID_SKILL.format(name=name), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The guard itself
# ---------------------------------------------------------------------------


def test_valid_utf8_within_the_cap_is_returned(tmp_path: Path) -> None:
    target = tmp_path / "f.json"
    target.write_bytes(b'{"ok": true}\n')
    assert read_guarded_text(target, max_bytes=1024, what="Thing") == '{"ok": true}\n'


def test_crlf_is_normalized_like_read_text_did(tmp_path: Path) -> None:
    """The guard replaced `read_text`, which applied universal newlines.

    Reading bytes and decoding skips that translation, so without normalizing
    a CRLF file would hand callers literal "\r\n" on Windows where they used
    to see "\n". Caught by CI on all four Windows jobs.
    """
    target = tmp_path / "f.json"
    target.write_bytes(b'{"ok":\r\n true}\r\n')
    assert read_guarded_text(target, max_bytes=1024, what="Thing") == '{"ok":\n true}\n'


def test_lone_carriage_return_is_also_normalized(tmp_path: Path) -> None:
    target = tmp_path / "f.json"
    target.write_bytes(b'{"ok":\r true}')
    assert read_guarded_text(target, max_bytes=1024, what="Thing") == '{"ok":\n true}'


def test_file_exactly_at_the_cap_is_accepted(tmp_path: Path) -> None:
    """The cap is inclusive. Off by one here rejects a legitimate file."""
    target = tmp_path / "f.json"
    target.write_bytes(b"a" * 100)
    assert read_guarded_text(target, max_bytes=100, what="Thing") == "a" * 100


def test_one_byte_over_the_cap_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "f.json"
    target.write_bytes(b"a" * 101)
    with pytest.raises(UntrustedInputError) as exc:
        read_guarded_text(target, max_bytes=100, what="Thing")
    assert "101 bytes" in str(exc.value)
    assert "100-byte" in str(exc.value)


def test_non_utf8_bytes_are_rejected_with_the_offset(tmp_path: Path) -> None:
    target = tmp_path / "f.json"
    target.write_bytes(b'{"a": "\xff\xfe"}')
    with pytest.raises(UntrustedInputError) as exc:
        read_guarded_text(target, max_bytes=1024, what="Thing")
    message = str(exc.value)
    assert "not valid UTF-8" in message
    assert "0xff" in message
    assert "offset 7" in message


def test_nul_byte_is_rejected(tmp_path: Path) -> None:
    """A NUL is the clearest signal that a text parser was handed a binary file."""
    target = tmp_path / "f.json"
    target.write_bytes(b'{"a": "b\x00c"}')
    with pytest.raises(UntrustedInputError) as exc:
        read_guarded_text(target, max_bytes=1024, what="Thing")
    assert "control character 0x00" in str(exc.value)


def test_escape_character_is_rejected(tmp_path: Path) -> None:
    """ESC is what turns a diagnostic into forged terminal output."""
    target = tmp_path / "f.json"
    target.write_text('{"a": "\x1b[31mred"}', encoding="utf-8")
    with pytest.raises(UntrustedInputError) as exc:
        read_guarded_text(target, max_bytes=1024, what="Thing")
    assert "control character 0x1b" in str(exc.value)


@pytest.mark.parametrize("whitespace", ["\t", "\n", "\r\n"])
def test_ordinary_whitespace_is_allowed(tmp_path: Path, whitespace: str) -> None:
    """Tab, newline, and carriage return are structure, not smuggling."""
    target = tmp_path / "f.json"
    target.write_bytes(f'{{"a":{whitespace}"b"}}'.encode())
    assert read_guarded_text(target, max_bytes=1024, what="Thing")


def test_high_unicode_is_not_treated_as_a_control_character(tmp_path: Path) -> None:
    """C1 code points are ordinary text; sanitization handles them at display."""
    target = tmp_path / "f.json"
    target.write_text('{"a": "café über 20 €"}', encoding="utf-8")
    assert read_guarded_text(target, max_bytes=1024, what="Thing")


def test_size_is_checked_before_the_file_is_read(tmp_path: Path) -> None:
    """An oversized file must be refused on stat, not decoded first.

    Non-UTF-8 content over the cap reports the size, which it could only do by
    failing before the decode step.
    """
    target = tmp_path / "f.json"
    target.write_bytes(b"\xff" * 200)
    with pytest.raises(UntrustedInputError) as exc:
        read_guarded_text(target, max_bytes=100, what="Thing")
    assert "200 bytes" in str(exc.value)
    assert "UTF-8" not in str(exc.value)


def test_caller_error_type_is_preserved(tmp_path: Path) -> None:
    target = tmp_path / "f.json"
    target.write_bytes(b"\xff")
    with pytest.raises(LedgerError):
        read_guarded_text(target, max_bytes=1024, what="Ledger", error_cls=LedgerError)


def test_os_errors_propagate_for_the_caller_to_word(tmp_path: Path) -> None:
    """Callers already wrap read failures with permission-specific wording."""
    with pytest.raises(OSError):
        read_guarded_text(tmp_path / "absent.json", max_bytes=1024, what="Thing")


def test_control_check_works_on_already_decoded_text() -> None:
    """stdin has no size to stat and arrives decoded, so it uses this half."""
    reject_control_characters('{"a": "b"}', what="Ingest payload", source="stdin")
    with pytest.raises(UntrustedInputError):
        reject_control_characters('{"a": "\x00"}', what="Ingest payload", source="stdin")


# ---------------------------------------------------------------------------
# Messages carry relative paths, never the host layout
# ---------------------------------------------------------------------------


def test_display_path_is_relative_for_a_file_under_the_cwd() -> None:
    assert display_path(REPO_ROOT / "README.md") in {"README.md", "./README.md"}


def test_rejection_message_does_not_leak_an_absolute_path(tmp_path: Path) -> None:
    """CI logs quote these verbatim; the build machine's layout is not useful."""
    target = tmp_path / "f.json"
    target.write_bytes(b"a" * 101)
    with pytest.raises(UntrustedInputError) as exc:
        read_guarded_text(target, max_bytes=100, what="Thing")
    assert str(tmp_path) not in str(exc.value)


# ---------------------------------------------------------------------------
# Each routed caller
# ---------------------------------------------------------------------------


def test_non_utf8_ledger_raises_instead_of_crashing(tmp_path: Path) -> None:
    ledger = tmp_path / ".skillcheck-history.json"
    ledger.write_bytes(b"\xff\xfe")
    with pytest.raises(LedgerError) as exc:
        load_ledger(ledger)
    assert "not valid UTF-8" in str(exc.value)


def test_nul_laden_ledger_is_rejected(tmp_path: Path) -> None:
    ledger = tmp_path / ".skillcheck-history.json"
    ledger.write_bytes(b'{"version": 1, "runs": [], "skill_path": "a\x00b"}')
    with pytest.raises(LedgerError) as exc:
        load_ledger(ledger)
    assert "control character" in str(exc.value)


def test_oversized_ledger_is_rejected(tmp_path: Path) -> None:
    ledger = tmp_path / ".skillcheck-history.json"
    ledger.write_bytes(b"a" * (MAX_LEDGER_BYTES + 1))
    with pytest.raises(LedgerError):
        load_ledger(ledger)


def test_non_utf8_config_raises_instead_of_crashing(tmp_path: Path) -> None:
    config = tmp_path / "skillcheck.toml"
    config.write_bytes(b"\xff\xfe")
    with pytest.raises(ConfigError) as exc:
        load_config(config)
    assert "not valid UTF-8" in str(exc.value)


def test_nul_laden_config_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "skillcheck.toml"
    config.write_bytes(b'[frontmatter]\nextension_fields = ["a\x00b"]\n')
    with pytest.raises(ConfigError) as exc:
        load_config(config)
    assert "control character" in str(exc.value)


def test_oversized_config_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "skillcheck.toml"
    config.write_bytes(b"a" * (MAX_CONFIG_BYTES + 1))
    with pytest.raises(ConfigError):
        load_config(config)


def test_valid_config_at_exactly_the_cap_still_loads(tmp_path: Path) -> None:
    """Padding to the cap with comment bytes must not trip the guard.

    Written as bytes, not text: write_text translates newlines on Windows, so a
    size computed from the string is three bytes short of what lands on disk and
    the test measures the wrong thing.
    """
    config = tmp_path / "skillcheck.toml"
    body = b'[frontmatter]\nextension_fields = ["x-team"]\n'
    padding = b"#" + b"p" * (MAX_CONFIG_BYTES - len(body) - 2) + b"\n"
    config.write_bytes(body + padding)
    assert config.stat().st_size == MAX_CONFIG_BYTES
    assert load_config(config).extension_fields == frozenset({"x-team"})


# ---------------------------------------------------------------------------
# End to end: exit 2, no traceback
# ---------------------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([*SKILLCHECK_CMD, *args], capture_output=True, text=True, cwd=REPO_ROOT)


def test_poisoned_discovered_config_exits_two_without_a_traceback(tmp_path: Path) -> None:
    """The worst case from the audit: no flag, just a bad file next to the skill.

    find_config walks up from the scanned path, so this used to crash any scan
    of a tree containing a binary skillcheck.toml.
    """
    skill = _skill(tmp_path / "proj", name="proj")
    (tmp_path / "proj" / "skillcheck.toml").write_bytes(b"\xff\xfe")
    result = _run(str(skill))
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "not valid UTF-8" in result.stderr


def test_poisoned_ledger_exits_two_without_a_traceback(tmp_path: Path) -> None:
    skill = _skill(tmp_path / "proj", name="proj")
    (tmp_path / "proj" / ".skillcheck-history.json").write_bytes(b"\xff\xfe")
    result = _run(str(skill), "--show-history")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "not valid UTF-8" in result.stderr


def test_nul_laden_ingest_response_exits_two(tmp_path: Path) -> None:
    skill = _skill(tmp_path / "proj", name="proj")
    response = tmp_path / "response.json"
    response.write_bytes(b'{"findings": [], "x": "a\x00b"}')
    result = _run(str(skill), "--ingest-critique", str(response))
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "control character" in result.stderr


def test_nul_laden_stdin_ingest_exits_two(tmp_path: Path) -> None:
    skill = _skill(tmp_path / "proj", name="proj")
    result = subprocess.run(
        [*SKILLCHECK_CMD, str(skill), "--ingest-critique", "-"],
        input='{"findings": [], "x": "a\x00b"}',
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "control character" in result.stderr
