"""Declarative description of the CLI mode flags and their incompatibilities.

One structure, four checks generated from it. Before this module the rules were
spread across four places in cli.py: a pairwise table, two hand-written dicts
mapping flags to argparse destinations, a multi-emit branch, and a ledger branch
in ``main`` outside the conflict function entirely. Adding a mode meant editing
all four and hoping none were missed.

The vocabulary:

- An **emit** mode replaces the report. It prints a prompt, a graph, or a set of
  activation hypotheses and exits without validating. Two emit modes cannot run
  at once because only one thing can be printed.
- An **augment** flag adds to the report. It cannot pair with an emit mode,
  because an emit mode produces no report to add to.
- A **ledger** flag reads or writes ``.skillcheck-history.json``. It records or
  reports a validation run, so it cannot pair with an emit mode either, and its
  two flags conflict with each other (one reads, one writes).

Emit-versus-emit, emit-versus-ledger, and ledger-versus-ledger conflicts follow
from the groups, so they are generated. Emit-versus-augment conflicts are listed
individually in ``PAIRWISE_CONFLICTS``: not every pair is disallowed, and the
ones that are carry wording explaining that specific combination.

``find_mode_conflict`` returns the message rather than printing and exiting, so
the whole table is testable in-process. cli.py owns the exit.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

GROUP_EMIT = "emit"
GROUP_AUGMENT = "augment"
GROUP_LEDGER = "ledger"


@dataclass(frozen=True, slots=True)
class ModeFlag:
    """One CLI mode flag and how to read it off the parsed arguments.

    Args:
        flag: The user-facing spelling, e.g. ``--emit-graph``.
        dest: The argparse destination holding its value.
        group: One of GROUP_EMIT, GROUP_AUGMENT, GROUP_LEDGER.
        takes_value: True when the flag stores a path rather than a bool, so
            presence is ``is not None`` rather than truthiness.
        suppressed_by: Flags whose presence takes this one out of its group.
            ``--agent-reason`` emits a prompt packet on its own but becomes an
            ingest modifier when paired with an ingest flag, so it is only an
            emit mode while neither is set.
    """

    flag: str
    dest: str
    group: str
    takes_value: bool = False
    suppressed_by: tuple[str, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class Conflict:
    """An emit/augment pair that cannot run together, with its explanation."""

    flag_a: str
    flag_b: str
    reason: str


# Declaration order is user-visible: the multi-emit message names the first two
# active emit modes in this order, and the ledger checks walk it as well.
MODE_FLAGS: tuple[ModeFlag, ...] = (
    ModeFlag("--emit-critique-prompt", "emit_critique_prompt", GROUP_EMIT),
    ModeFlag("--emit-graph", "emit_graph", GROUP_EMIT),
    ModeFlag("--emit-graph-prompt", "emit_graph_prompt", GROUP_EMIT),
    ModeFlag("--activation-hypotheses", "activation_hypotheses", GROUP_EMIT),
    ModeFlag(
        "--agent-reason",
        "agent_reason",
        GROUP_EMIT,
        suppressed_by=("--ingest-critique", "--ingest-graph"),
    ),
    ModeFlag("--analyze-graph", "analyze_graph", GROUP_AUGMENT),
    ModeFlag("--ingest-critique", "ingest_critique", GROUP_AUGMENT, takes_value=True),
    ModeFlag("--ingest-graph", "ingest_graph", GROUP_AUGMENT, takes_value=True),
    ModeFlag("--history", "history", GROUP_LEDGER),
    ModeFlag("--show-history", "show_history", GROUP_LEDGER),
)

_BY_FLAG: dict[str, ModeFlag] = {mode.flag: mode for mode in MODE_FLAGS}


# Emit/augment pairs that are disallowed. Order within a pair does not matter to
# detection; it only decides which flag the wording leads with.
PAIRWISE_CONFLICTS: tuple[Conflict, ...] = (
    Conflict(
        "--emit-critique-prompt", "--ingest-critique",
        "Cannot use --emit-critique-prompt and --ingest-critique together. "
        "Pick one: emit a prompt for your agent to execute, or ingest the agent's response.",
    ),
    Conflict(
        "--emit-graph", "--analyze-graph",
        "Cannot use --emit-graph with --analyze-graph. "
        "--emit-graph is an emit mode (replaces the report). "
        "--analyze-graph is an augment mode (adds to the report).",
    ),
    Conflict(
        "--emit-graph", "--ingest-critique",
        "Cannot use --emit-graph with --ingest-critique. "
        "--emit-graph replaces the report; --ingest-critique augments it.",
    ),
    Conflict(
        "--emit-graph-prompt", "--ingest-critique",
        "Cannot use --emit-graph-prompt with --ingest-critique. "
        "--emit-graph-prompt is an emit mode; --ingest-critique is an augment mode.",
    ),
    Conflict(
        "--emit-graph-prompt", "--analyze-graph",
        "Cannot use --emit-graph-prompt with --analyze-graph. "
        "--emit-graph-prompt is an emit mode; --analyze-graph is an augment mode.",
    ),
    Conflict(
        "--emit-graph-prompt", "--ingest-graph",
        "Cannot use --emit-graph-prompt with --ingest-graph. "
        "--emit-graph-prompt emits a prompt; --ingest-graph ingests the agent's response. "
        "Use them in separate invocations.",
    ),
    Conflict(
        "--ingest-graph", "--emit-graph",
        "Cannot use --ingest-graph with --emit-graph. "
        "--emit-graph replaces the report; --ingest-graph augments it.",
    ),
    Conflict(
        "--ingest-graph", "--emit-critique-prompt",
        "Cannot use --ingest-graph with --emit-critique-prompt. "
        "--emit-critique-prompt is an emit mode; --ingest-graph is an augment mode.",
    ),
    Conflict(
        "--ingest-graph", "--analyze-graph",
        "Cannot use --ingest-graph with --analyze-graph. "
        "--ingest-graph supersedes heuristic-only graph analysis.",
    ),
)


def _is_set(args: argparse.Namespace, mode: ModeFlag) -> bool:
    """Whether the flag was given at all, ignoring group suppression."""
    value = getattr(args, mode.dest, None)
    return value is not None if mode.takes_value else bool(value)


def active_flags(args: argparse.Namespace) -> dict[str, bool]:
    """Map every mode flag to whether it is active in its declared group.

    A suppressed flag reports False: ``--agent-reason`` alongside an ingest flag
    is not acting as an emit mode, so it must not trip the emit checks.
    """
    given = {mode.flag: _is_set(args, mode) for mode in MODE_FLAGS}
    return {
        mode.flag: given[mode.flag] and not any(given[other] for other in mode.suppressed_by)
        for mode in MODE_FLAGS
    }


def _flags_in_group(group: str) -> tuple[str, ...]:
    return tuple(mode.flag for mode in MODE_FLAGS if mode.group == group)


def find_mode_conflict(args: argparse.Namespace) -> str | None:
    """Return the message for the first conflict found, or None if there is none.

    Check order is user-visible when several conflicts apply at once, and is
    preserved from the hand-written version: multiple emit modes first (it has
    a dedicated message), then the emit/augment table, then emit against the
    ledger flags, then the two ledger flags against each other.
    """
    active = active_flags(args)

    active_emits = [flag for flag in _flags_in_group(GROUP_EMIT) if active[flag]]
    if len(active_emits) > 1:
        return (
            f"Cannot use {' and '.join(active_emits[:2])} together. "
            f"Pick one emit mode."
        )

    for conflict in PAIRWISE_CONFLICTS:
        if active[conflict.flag_a] and active[conflict.flag_b]:
            return conflict.reason

    for emit_flag in active_emits:
        if active["--history"]:
            return (
                f"Cannot use --history with {emit_flag}. "
                f"--history records validation runs; emit modes skip validation."
            )
        if active["--show-history"]:
            return (
                f"Cannot use --show-history with {emit_flag}. "
                f"--show-history reads the ledger; {emit_flag} emits a prompt."
            )

    if active["--show-history"] and active["--history"]:
        return (
            "Cannot use --show-history with --history. "
            "--show-history reads the ledger; --history writes to it. Pick one."
        )

    return None


__all__ = [
    "GROUP_AUGMENT",
    "GROUP_EMIT",
    "GROUP_LEDGER",
    "MODE_FLAGS",
    "PAIRWISE_CONFLICTS",
    "Conflict",
    "ModeFlag",
    "active_flags",
    "find_mode_conflict",
]
