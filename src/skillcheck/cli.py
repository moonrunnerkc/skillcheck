from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skillcheck import __version__
from skillcheck import config as runtime_config
from skillcheck.commands import (
    emit_activation,
    emit_agent_reason_packet,
    emit_critique_prompts,
    emit_graph,
    emit_graph_prompts,
    resolve_paths,
    run_show_history,
    run_validation,
)
from skillcheck.config_loader import ConfigError, find_config, load_config
from skillcheck.modes import find_mode_conflict

# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

_EPILOG = """\
examples:
  skillcheck SKILL.md                        validate a single file
  skillcheck skills/                          scan a directory recursively
  skillcheck SKILL.md --format json           machine-readable output for CI
  skillcheck SKILL.md --max-lines 800         override sizing thresholds
  skillcheck SKILL.md --ignore frontmatter    suppress a rule category
  skillcheck SKILL.md --min-desc-score 50     require minimum description quality
  skillcheck SKILL.md --target-agent vscode   scope checks to VS Code
  skillcheck SKILL.md --strict-vscode         treat VS Code issues as errors
  skillcheck SKILL.md --target-agent cursor   scope checks to Cursor
  skillcheck SKILL.md --strict-cursor         treat Cursor issues as errors
  skillcheck SKILL.md --strict                treat all warnings as errors (umbrella)
  skillcheck SKILL.md --skip-ref-check        skip file reference validation
  skillcheck SKILL.md --emit-critique-prompt  print prompt for agent self-critique
  skillcheck SKILL.md --ingest-critique r.json  ingest agent response and merge diagnostics
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillcheck",
        description="Cross-agent skill quality gate for SKILL.md files. Validates against the agentskills.io spec.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        nargs="+",
        type=Path,
        help="Path to a SKILL.md file or a directory to scan recursively. Multiple paths accepted.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "md", "agent", "github"],
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=None,
        metavar="N",
        help="Override the line-count threshold (default: 500).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        metavar="N",
        help="Override the token-count threshold (default: 8000).",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        dest="ignore_prefixes",
        metavar="PREFIX",
        default=[],
        help="Suppress rules matching this prefix. Can be repeated.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="Disable colored output.",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        default=False,
        help="Suppress all output. Only the exit code indicates result.",
    )
    parser.add_argument(
        "--skip-dirname-check",
        action="store_true",
        default=False,
        help="Skip directory-name matching check (useful for CI temp paths).",
    )
    parser.add_argument(
        "--skip-ref-check",
        action="store_true",
        default=False,
        help="Skip file reference validation (useful when referenced files are unavailable).",
    )
    parser.add_argument(
        "--min-desc-score",
        type=int,
        default=None,
        metavar="N",
        help="Minimum description quality score (0-100). Below this triggers a warning.",
    )
    parser.add_argument(
        "--explain-score",
        action="store_true",
        default=False,
        help="Show per-dimension breakdown for description quality scores.",
    )
    parser.add_argument(
        "--target-agent",
        choices=["claude", "vscode", "cursor", "all"],
        default="all",
        help="Scope compatibility checks to a specific agent (default: all).",
    )
    parser.add_argument(
        "--strict-vscode",
        action="store_true",
        default=False,
        help="Promote VS Code compatibility issues to errors.",
    )
    parser.add_argument(
        "--strict-cursor",
        action="store_true",
        default=False,
        help="Promote Cursor compatibility issues to errors.",
    )
    parser.add_argument(
        "--strict",
        dest="strict_all",
        action="store_true",
        default=False,
        help=(
            "Strict mode. Escalates warning-only runs to exit 1, "
            "promotes VS Code compatibility to errors (same as --strict-vscode), "
            "promotes Cursor compatibility to errors (same as --strict-cursor), "
            "and enables the 'all' field in config for future strict rules."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to skillcheck.toml. Defaults to the nearest skillcheck.toml from the target path upward.",
    )
    parser.add_argument(
        "--semantic",
        action="store_true",
        default=False,
        help="Run semantic-adjacent validation. Implies --analyze-graph when --ingest-graph is not supplied.",
    )
    parser.add_argument(
        "--agent-reason",
        action="store_true",
        default=False,
        help="Agent-native workflow shortcut. Without ingested responses, emits an agent prompt packet and exits 0.",
    )
    parser.add_argument(
        "--emit-critique-prompt",
        action="store_true",
        default=False,
        help=(
            "Print the agent self-critique prompt to stdout and exit 0. "
            "Skips all symbolic validation. Use --format json to wrap in {\"prompt\": \"...\"}."
        ),
    )
    parser.add_argument(
        "--ingest-critique",
        metavar="PATH",
        default=None,
        help=(
            "Read an agent self-critique JSON response from PATH (use - for stdin), "
            "convert to diagnostics, merge with symbolic results, and emit a unified report. "
            "Exit code 3 signals semantic drift when symbolic validation passed."
        ),
    )
    parser.add_argument(
        "--critique-agent",
        choices=["claude", "codex", "cursor"],
        default=None,
        metavar="NAME",
        help=(
            "Agent variant for the self-critique prompt (claude, codex, cursor; default: claude). "
            "Requires --emit-critique-prompt or --ingest-critique."
        ),
    )
    parser.add_argument(
        "--emit-graph",
        action="store_true",
        default=False,
        help=(
            "Print the extracted capability graph to stdout and exit 0. "
            "Replaces the validation report. Use --format json for machine-readable output."
        ),
    )
    parser.add_argument(
        "--analyze-graph",
        action="store_true",
        default=False,
        help=(
            "Extract the capability graph, run graph analyzers, and merge diagnostics "
            "into the validation report. Augments (does not replace) the report."
        ),
    )
    parser.add_argument(
        "--emit-graph-prompt",
        action="store_true",
        default=False,
        help=(
            "Print the graph-extraction prompt to stdout and exit 0. "
            "Hand the output to an agent, then use --ingest-graph with the response. "
            "Mutually exclusive with all other emit and augment modes."
        ),
    )
    parser.add_argument(
        "--ingest-graph",
        metavar="PATH",
        default=None,
        help=(
            "Read an agent graph-extraction JSON response from PATH (use - for stdin), "
            "build a CapabilityGraph, run graph analyzers and divergence analyzers, and "
            "merge all diagnostics into the report. Compatible with --ingest-critique. "
            "Supersedes --analyze-graph (which does heuristic-only analysis)."
        ),
    )
    parser.add_argument(
        "--graph-agent",
        choices=["claude", "codex", "cursor"],
        default=None,
        metavar="NAME",
        help=(
            "Agent variant for the graph-extraction prompt (claude, codex, cursor; default: claude). "
            "Requires --emit-graph-prompt or --ingest-graph."
        ),
    )
    parser.add_argument(
        "--history",
        action="store_true",
        default=False,
        help=(
            "Append a validation record to the per-skill .skillcheck-history.json ledger "
            "next to the SKILL.md file. Off by default. Incompatible with emit modes."
        ),
    )
    parser.add_argument(
        "--show-history",
        action="store_true",
        default=False,
        help=(
            "Print the validation history ledger for the skill and exit 0. "
            "Skips all validation. Use --format json for machine-readable output. "
            "Incompatible with emit modes and with --history."
        ),
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        default=False,
        help=(
            "Exit 1 when --history is active and a regression is detected "
            "(history.skill.regressed fires). Without this flag, regressions are "
            "warnings that do not affect the exit code. Independent of --strict."
        ),
    )
    parser.add_argument(
        "--activation-hypotheses",
        action="store_true",
        default=False,
        help=(
            "Experimental emit mode. Generate likely natural-language activation triggers "
            "for the skill and exit 0."
        ),
    )
    return parser


# ---------------------------------------------------------------------------
# Config application
# ---------------------------------------------------------------------------


def _apply_config(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Apply skillcheck.toml defaults to parsed args."""
    config_path = args.config or find_config(args.path[0])
    try:
        loaded_config = load_config(config_path)
    except ConfigError as exc:
        parser.error(str(exc))
    if config_path is not None:
        print(f"Loaded config from {config_path}", file=sys.stderr)

    runtime_config.set_extension_fields(loaded_config.extension_fields)
    if loaded_config.reserved_words is not None:
        runtime_config.set_reserved_words(loaded_config.reserved_words)

    if loaded_config.format is not None and args.format == "text":
        args.format = loaded_config.format
    if loaded_config.max_lines is not None and args.max_lines is None:
        args.max_lines = loaded_config.max_lines
    if loaded_config.max_tokens is not None and args.max_tokens is None:
        args.max_tokens = loaded_config.max_tokens
    if loaded_config.min_desc_score is not None and args.min_desc_score is None:
        args.min_desc_score = loaded_config.min_desc_score
    if loaded_config.target_agent is not None and args.target_agent == "all":
        args.target_agent = loaded_config.target_agent
    if loaded_config.strict_vscode is True:
        args.strict_vscode = True
    if loaded_config.strict_cursor is True:
        args.strict_cursor = True
    if loaded_config.strict_all is True:
        args.strict_all = True
    if loaded_config.skip_dirname_check is True:
        args.skip_dirname_check = True
    if loaded_config.skip_ref_check is True:
        args.skip_ref_check = True
    if loaded_config.ignore and not args.ignore_prefixes:
        args.ignore_prefixes = list(loaded_config.ignore)
    if loaded_config.analyze_graph is True:
        args.analyze_graph = True
    if loaded_config.semantic is True:
        args.semantic = True
    if loaded_config.history is True:
        args.history = True
    if loaded_config.critique_agent is not None and args.critique_agent is None:
        args.critique_agent = loaded_config.critique_agent
    if loaded_config.graph_agent is not None and args.graph_agent is None:
        args.graph_agent = loaded_config.graph_agent


# ---------------------------------------------------------------------------
# Mode conflict resolution
#
# The flags, their groups, and every incompatibility live in skillcheck.modes.
# This function only turns a detected conflict into stderr plus exit 2.
# ---------------------------------------------------------------------------


def _die_on_mode_conflict(args: argparse.Namespace) -> None:
    """Exit 2 with a diagnostic if the requested modes cannot run together."""
    message = find_mode_conflict(args)
    if message is not None:
        print(message, file=sys.stderr)
        sys.exit(2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    # Ensure UTF-8 output on Windows where the default encoding may be cp1252.
    if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    if sys.stderr.encoding and sys.stderr.encoding.lower().replace("-", "") != "utf8":
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    parser = _build_parser()
    args = parser.parse_args()
    _apply_config(args, parser)

    # --strict: enable all strict modes.
    if args.strict_all:
        args.strict_vscode = True
        args.strict_cursor = True

    if args.format not in {"text", "json", "md", "agent", "github"}:
        parser.error("format must be one of: text, json, md, agent, github")
    if args.target_agent not in {"claude", "vscode", "cursor", "all"}:
        parser.error("target-agent must be one of: claude, vscode, cursor, all")
    if args.critique_agent is not None and args.critique_agent not in {"claude", "codex", "cursor"}:
        parser.error("critique-agent must be one of: claude, codex, cursor")
    if args.graph_agent is not None and args.graph_agent not in {"claude", "codex", "cursor"}:
        parser.error("graph-agent must be one of: claude, codex, cursor")

    if args.semantic and args.ingest_graph is None:
        args.analyze_graph = True

    _die_on_mode_conflict(args)

    agent_id = args.critique_agent or "claude"
    graph_agent_id = args.graph_agent or "claude"

    if args.critique_agent is not None and not args.emit_critique_prompt and not args.agent_reason and args.ingest_critique is None:
        parser.error("--critique-agent requires --emit-critique-prompt or --ingest-critique")

    if args.graph_agent is not None and not args.emit_graph_prompt and not args.agent_reason and args.ingest_graph is None:
        parser.error("--graph-agent requires --emit-graph-prompt or --ingest-graph")

    paths = resolve_paths(args)

    # --show-history: read the ledger for the first path, print it, and exit.
    if args.show_history:
        run_show_history(args, paths)

    # --emit-graph: emit the heuristic graph and skip symbolic validation entirely
    if args.emit_graph:
        emit_graph(paths, fmt=args.format)
        sys.exit(0)

    # --emit-critique-prompt: skip symbolic validation entirely
    if args.emit_critique_prompt:
        emit_critique_prompts(paths, fmt=args.format, agent_id=agent_id)
        sys.exit(0)

    # --emit-graph-prompt: render and print the graph-extraction prompt, then exit
    if args.emit_graph_prompt:
        emit_graph_prompts(paths, fmt=args.format, agent_id=graph_agent_id)
        sys.exit(0)

    if args.agent_reason and args.ingest_critique is None and args.ingest_graph is None:
        emit_agent_reason_packet(paths, args.format, agent_id, graph_agent_id)
        sys.exit(0)

    if args.activation_hypotheses:
        emit_activation(paths, args.format)
        sys.exit(0)

    run_validation(args, paths, agent_id, graph_agent_id)
