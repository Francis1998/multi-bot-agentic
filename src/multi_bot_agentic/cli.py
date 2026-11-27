"""Command-line interface for multi-bot-agentic."""

from __future__ import annotations

import argparse
import getpass
import json
import math
import os
import sqlite3
import sys
from collections.abc import Iterable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import replace
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from multi_bot_agentic.approval import (
    ApprovalDecision,
    ApprovalError,
    AwaitingApprovalError,
    InterruptRecord,
    collect_interrupts,
    decide_interrupt,
    find_interrupt,
    paused_interrupt,
)
from multi_bot_agentic.bots import BotRegistryError, BotSpec, load_bot_registry
from multi_bot_agentic.config import AppConfig, build_llm_adapter
from multi_bot_agentic.event_log import EventRecord, SQLiteEventLog
from multi_bot_agentic.fork import (
    RUN_FORKED,
    ForkError,
    RunHistory,
    build_history,
    fork_children,
    inherited_events_intact,
    parse_lineage,
    plan_fork,
)
from multi_bot_agentic.mcp import McpConfigError, McpServerStatus, McpToolset, load_mcp_config
from multi_bot_agentic.models import ToolSpec
from multi_bot_agentic.pricing import PriceTable, PriceTableError
from multi_bot_agentic.runner import (
    AgentRunner,
    ResumeError,
    RunBusyError,
    RunResult,
    build_default_tools,
    fork_usage,
    recorded_outcome,
)
from multi_bot_agentic.safety import SafetyPolicy, parse_approval_patterns
from multi_bot_agentic.structured_output import (
    DEFAULT_OUTPUT_RETRIES,
    MAX_OUTPUT_RETRIES,
    OutputContract,
    OutputSchema,
    SchemaError,
    failed_attempts,
    recorded_contract,
    recorded_output,
    write_output_file,
)
from multi_bot_agentic.tools.base import ToolAdapter
from multi_bot_agentic.usage import UsageLimits, UsageTotals, format_number, usage_summary

MCP_CONFIG_HELP = "MCP servers JSON (Claude Desktop 'mcpServers' format); tools appear as mcp__<server>__<tool>"
BOTS_HELP = 'bot registry JSON: {"bots": {"<id>": {"allowed_tools": [...], "name": "...", "description": "..."}}}'
TRACE_FORMATS = ("otlp-json", "mermaid")
# How many of the log's runs an unknown-run error names.
RECENT_RUNS_SHOWN = 5
REQUIRE_APPROVAL_HELP = (
    "pause before calling these tools until a human approves or rejects the call: tool names or fnmatch "
    "patterns such as 'mcp__*', comma-separated, repeatable (replaces MULTIBOT_REQUIRE_APPROVAL)"
)
# Exit code of run, fork, and resume when the run paused at a human-approval interrupt.
EXIT_AWAITING_APPROVAL = 3
# Exit code of run, fork, and resume when another live process is continuing the run (sysexits
# EX_TEMPFAIL: nothing was written; try again once that process has finished).
EXIT_RUN_BUSY = 75
# Exit code of run, fork, and resume when the final answer never validated against --output-schema.
EXIT_OUTPUT_INVALID = 4
OUTPUT_SCHEMA_HELP = (
    "JSON Schema (a documented subset) the final answer must validate against; the answer must be a JSON "
    "document, and invalid answers get correction rounds"
)
OUTPUT_RETRIES_HELP = (
    f"correction rounds after an invalid final answer (0-{MAX_OUTPUT_RETRIES}, default {DEFAULT_OUTPUT_RETRIES})"
)
OUTPUT_FILE_HELP = "write the validated output to this file (atomically, as indented JSON) when the run succeeds"
# The event log and the files SQLite keeps next to it; --output-file may name none of them.
SQLITE_FILE_SUFFIXES = ("", "-wal", "-shm", "-journal")
# Exit code of run, fork, and resume when a usage limit stopped the run (resume it with a higher limit).
EXIT_USAGE_LIMIT = 5
RESET_LIMITS_HELP = "drop the usage limits recorded {where}; only this command's --max-* flags apply"
# Usage-limit flag -> UsageLimits field and help text.
USAGE_LIMIT_FLAGS: dict[str, tuple[str, str]] = {
    "--max-requests": ("max_requests", "stop before a model call beyond N calls"),
    "--max-input-tokens": ("max_input_tokens", "stop when input tokens (cached included) exceed N"),
    "--max-output-tokens": ("max_output_tokens", "stop when output tokens (reasoning included) exceed N"),
    "--max-total-tokens": ("max_total_tokens", "stop when total tokens exceed N"),
    "--max-cost-usd": ("max_cost_usd", "stop when the run's cost in USD exceeds this amount"),
}


class McpStartupError(RuntimeError):
    """Raised when a configured MCP server cannot be started for a run."""


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Arguments (default: ``sys.argv[1:]``).

    Returns:
        Process exit code.
    """

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_command(args)
    if args.command == "replay":
        return replay_command(args)
    if args.command == "report":
        return report_command(args)
    if args.command == "resume":
        return resume_command(args)
    if args.command == "eval":
        return eval_command(args)
    if args.command == "mcp-tools":
        return mcp_tools_command(args)
    if args.command == "trace":
        return trace_command(args)
    if args.command == "history":
        return history_command(args)
    if args.command == "fork":
        return fork_command(args)
    if args.command == "approvals":
        return approvals_command(args)
    if args.command == "approve":
        return decide_command(args, ApprovalDecision.APPROVED)
    if args.command == "reject":
        return decide_command(args, ApprovalDecision.REJECTED)
    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured argument parser.
    """

    parser = argparse.ArgumentParser(description="Deterministic AI-agent orchestrator")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="run an Observe-Decide-Act agent loop")
    run_parser.add_argument("--goal", required=True, help="goal to execute")
    run_parser.add_argument("--provider", default=None, help="fake, openai, claude_code, gemini, kimi")
    run_parser.add_argument("--event-log", type=Path, default=None, help="sqlite event log path")
    run_parser.add_argument("--max-steps", type=int, default=None, help="maximum loop steps")
    run_parser.add_argument("--run-id", default=None, help="optional run id")
    run_parser.add_argument("--mcp-config", type=Path, default=None, help=MCP_CONFIG_HELP)
    run_parser.add_argument("--require-approval", action="append", metavar="TOOL[,TOOL]", help=REQUIRE_APPROVAL_HELP)
    run_parser.add_argument("--output-schema", type=Path, default=None, metavar="PATH", help=OUTPUT_SCHEMA_HELP)
    run_parser.add_argument("--output-retries", type=_retries, default=None, metavar="N", help=OUTPUT_RETRIES_HELP)
    run_parser.add_argument("--output-file", type=Path, default=None, metavar="PATH", help=OUTPUT_FILE_HELP)
    add_usage_limit_flags(run_parser)

    replay_parser = subparsers.add_parser("replay", help="print durable event log")
    replay_parser.add_argument("--event-log", type=Path, required=True, help="sqlite event log path")
    replay_parser.add_argument("--run-id", default=None, help="optional run id")
    replay_parser.add_argument("--event-type", default=None, help="optional event type filter")
    replay_parser.add_argument("--format", choices=("json", "text"), default="json", help="output format")

    report_parser = subparsers.add_parser("report", help="summarize one or more event-log runs")
    report_parser.add_argument("--event-log", type=Path, required=True, help="sqlite event log path")
    report_parser.add_argument("--run-id", default=None, help="optional run id")

    resume_parser = subparsers.add_parser("resume", help="resume a run from its latest checkpoint")
    resume_parser.add_argument("--run-id", required=True, help="run id to resume")
    resume_parser.add_argument("--event-log", type=Path, required=True, help="sqlite event log path")
    resume_parser.add_argument("--provider", default=None, help="fake, openai, claude_code, gemini, kimi")
    resume_parser.add_argument("--max-steps", type=int, default=None, help="maximum loop steps")
    resume_parser.add_argument("--mcp-config", type=Path, default=None, help=MCP_CONFIG_HELP)
    resume_parser.add_argument(
        "--require-approval",
        action="append",
        metavar="TOOL[,TOOL]",
        help="more tools that need approval; the run's recorded approval policy always stays in force",
    )
    resume_parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        metavar="PATH",
        help=OUTPUT_FILE_HELP + " (the run's recorded output schema stays in force)",
    )
    add_usage_limit_flags(resume_parser, " (replaces the run's recorded limit)")
    resume_parser.add_argument(
        "--reset-usage-limits", action="store_true", help=RESET_LIMITS_HELP.format(where="in the run")
    )
    eval_parser = subparsers.add_parser("eval", help="run offline golden-path evaluation fixtures")
    eval_parser.add_argument("--fixtures", type=Path, default=None, help="fixture directory")
    eval_parser.add_argument(
        "--event-log-dir",
        type=Path,
        default=Path("data/eval-logs"),
        help="per-scenario sqlite dir",
    )
    mcp_parser = subparsers.add_parser("mcp-tools", help="start configured MCP servers and list their tools")
    mcp_parser.add_argument("--mcp-config", type=Path, required=True, help=MCP_CONFIG_HELP)
    mcp_parser.add_argument("--format", choices=("text", "json"), default="text", help="output format")

    trace_parser = subparsers.add_parser(
        "trace",
        help="export a recorded run as an OpenTelemetry GenAI trace (OTLP/JSON) or a Mermaid sequence diagram",
    )
    trace_parser.add_argument("--event-log", type=Path, required=True, help="sqlite event log path")
    trace_parser.add_argument("--run-id", default=None, help="run id (default: the most recently active run)")
    trace_parser.add_argument(
        "--format",
        choices=TRACE_FORMATS,
        default=None,
        help="output format (default otlp-json; with only --otlp-endpoint nothing is printed)",
    )
    trace_parser.add_argument("--output", type=Path, default=None, help="write the output to this file, not stdout")
    trace_parser.add_argument(
        "--include-content",
        action="store_true",
        help="also export the goal, model inputs/outputs, tool arguments/results, and handoff summaries (redacted)",
    )
    trace_parser.add_argument("--agent-name", default=None, help="gen_ai.agent.name of the root invoke_agent span")
    trace_parser.add_argument(
        "--otlp-endpoint",
        default=None,
        help="also POST the trace as OTLP/JSON to this URL, e.g. http://localhost:4318/v1/traces",
    )
    trace_parser.add_argument(
        "--otlp-header",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="OTLP request header (repeatable); ${VAR} expands from the environment; values are never printed",
    )
    trace_parser.add_argument(
        "--otlp-timeout",
        type=float,
        default=10.0,
        help="OTLP request timeout in seconds (default 10)",
    )

    history_parser = subparsers.add_parser(
        "history", help="list the steps of a recorded run and the steps a fork can continue after"
    )
    history_parser.add_argument("--event-log", type=Path, required=True, help="sqlite event log path")
    history_parser.add_argument("--run-id", default=None, help="run id (default: the most recently active run)")
    history_parser.add_argument("--format", choices=("text", "json"), default="text", help="output format")

    fork_parser = subparsers.add_parser(
        "fork", help="branch a recorded run after step N into a new run and continue it (time travel)"
    )
    fork_parser.add_argument("--event-log", type=Path, required=True, help="sqlite event log path (the fork is added)")
    fork_parser.add_argument("--run-id", required=True, help="run to branch from (it is not modified)")
    fork_parser.add_argument(
        "--at-step",
        type=_step_number,
        required=True,
        help="continue after this step; 0 starts over from the goal (see `history`)",
    )
    fork_parser.add_argument("--new-run-id", required=True, help="run id of the fork (must not exist yet)")
    fork_parser.add_argument("--goal", default=None, help="new goal; the model answers it before earlier directives")
    fork_parser.add_argument(
        "--provider", default=None, help="fake, openai, claude_code, gemini, kimi (default: MULTIBOT_PROVIDER or fake)"
    )
    fork_parser.add_argument("--bot", default=None, help="registered bot to continue as (needs --bots)")
    fork_parser.add_argument("--bots", type=Path, default=None, help=BOTS_HELP)
    fork_parser.add_argument(
        "--max-steps", type=int, default=None, help="step budget of the fork, inherited steps included"
    )
    fork_parser.add_argument("--mcp-config", type=Path, default=None, help=MCP_CONFIG_HELP)
    fork_parser.add_argument(
        "--dry-run", action="store_true", help="print the rebuilt state and the first decision; write nothing"
    )
    fork_parser.add_argument(
        "--require-approval",
        action="append",
        metavar="TOOL[,TOOL]",
        help="more tools that need approval; the source run's approval policy is inherited",
    )
    fork_parser.add_argument(
        "--output-schema",
        type=Path,
        default=None,
        metavar="PATH",
        help="new output schema for the fork (default: the source run's, if any)",
    )
    fork_parser.add_argument(
        "--output-retries",
        type=_retries,
        default=None,
        metavar="N",
        help="new correction-round budget (default: the source run's); inherited failed answers count",
    )
    fork_parser.add_argument("--output-file", type=Path, default=None, metavar="PATH", help=OUTPUT_FILE_HELP)
    add_usage_limit_flags(fork_parser, " (counts inherited usage; replaces the inherited limit)")
    fork_parser.add_argument(
        "--reset-usage-limits", action="store_true", help=RESET_LIMITS_HELP.format(where="at the fork point")
    )

    approvals_parser = subparsers.add_parser("approvals", help="list or show human-approval interrupts")
    approvals_sub = approvals_parser.add_subparsers(dest="approvals_command", required=True)
    list_parser = approvals_sub.add_parser("list", help="list interrupts (default: pending ones)")
    list_parser.add_argument("--event-log", type=Path, required=True, help="sqlite event log path")
    list_parser.add_argument("--run-id", default=None, help="only this run")
    list_parser.add_argument("--all", action="store_true", help="include decided and expired interrupts")
    list_parser.add_argument("--format", choices=("text", "json"), default="text", help="output format")
    show_parser = approvals_sub.add_parser("show", help="show one interrupt with its arguments and decision")
    show_parser.add_argument("interrupt_id", help="interrupt id (int-...)")
    show_parser.add_argument("--event-log", type=Path, required=True, help="sqlite event log path")
    show_parser.add_argument("--run-id", default=None, help="run to look in (only needed for ambiguous ids)")
    show_parser.add_argument("--format", choices=("text", "json"), default="text", help="output format")

    for name, verb in (("approve", "approve"), ("reject", "reject")):
        decide_parser = subparsers.add_parser(name, help=f"{verb} the tool call a paused run is waiting on")
        decide_parser.add_argument(
            "interrupt_id", nargs="?", default=None, help="interrupt id (default: the one --run-id is paused at)"
        )
        decide_parser.add_argument("--event-log", type=Path, required=True, help="sqlite event log path")
        decide_parser.add_argument("--run-id", default=None, help="run whose paused interrupt to decide")
        decide_parser.add_argument("--by", default=None, help="who decides (default: the OS user)")
        if name == "approve":
            decide_parser.add_argument("--reason", default=None, help="why (optional, recorded)")
            decide_parser.add_argument(
                "--args",
                default=None,
                metavar="JSON",
                help='replacement arguments: a JSON object with the same keys and types, e.g. \'{"text": "..."}\'',
            )
        else:
            decide_parser.add_argument(
                "--reason", required=True, help="why; recorded and shown to the model so it can re-plan"
            )
    return parser


def add_usage_limit_flags(parser: argparse.ArgumentParser, note: str = "") -> None:
    """Add the ``--max-requests`` / ``--max-*-tokens`` / ``--max-cost-usd`` flags to ``parser``."""

    for flag, (dest, text) in USAGE_LIMIT_FLAGS.items():
        is_cost = dest == "max_cost_usd"
        parser.add_argument(
            flag,
            dest=dest,
            type=_usd if is_cost else _token_count,
            default=None,
            metavar="USD" if is_cost else "N",
            help=f"{text}{note}",
        )


def usage_limits_from_args(args: argparse.Namespace) -> UsageLimits:
    """Return the usage limits set by the command's flags (unset flags leave a counter unlimited)."""

    values = {dest: getattr(args, dest, None) for dest, _ in USAGE_LIMIT_FLAGS.values()}
    return UsageLimits(**{name: value for name, value in values.items() if value is not None})


def _token_count(value: str) -> int:
    """Parse a token or request limit: an integer >= 0."""

    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be an integer >= 0, got {value!r}") from None
    if number < 0:
        raise argparse.ArgumentTypeError(f"must be an integer >= 0, got {value!r}")
    return number


def _usd(value: str) -> float:
    """Parse a cost limit: a finite number of USD >= 0."""

    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be a number of USD >= 0, got {value!r}") from None
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError(f"must be a number of USD >= 0, got {value!r}")
    return number


def _step_number(value: str) -> int:
    """Parse a ``--at-step`` value: an integer >= 0."""

    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be an integer >= 0, got {value!r}") from None
    if number < 0:
        raise argparse.ArgumentTypeError(f"must be an integer >= 0, got {value!r}")
    return number


def _retries(value: str) -> int:
    """Parse an ``--output-retries`` value: an integer from 0 to ``MAX_OUTPUT_RETRIES``."""

    try:
        number = int(value)
    except ValueError:
        number = -1
    if not 0 <= number <= MAX_OUTPUT_RETRIES:
        raise argparse.ArgumentTypeError(f"must be an integer from 0 to {MAX_OUTPUT_RETRIES}, got {value!r}")
    return number


def check_output_file(path: Path | None, event_log: Path) -> None:
    """Refuse an ``--output-file`` that names a directory or the event log before anything runs.

    Writing the output over the SQLite database, or over one of the files SQLite keeps next to it
    (``-wal``, ``-shm``, ``-journal``), would destroy the run history that recorded it.

    Raises:
        ValueError: If ``path`` is an existing directory, the event log, or one of its SQLite files.
    """

    if path is None:
        return
    if path.is_dir():
        raise ValueError(f"--output-file {path} is a directory; name a file")
    target = path.resolve()
    for suffix in SQLITE_FILE_SUFFIXES:
        database_file = Path(f"{event_log}{suffix}")
        if target == database_file.resolve() or (
            path.exists() and database_file.exists() and os.path.samefile(path, database_file)
        ):
            raise ValueError(f"--output-file {path} is the event log or one of its SQLite files; choose another path")


def output_contract_from_args(args: argparse.Namespace) -> OutputContract | None:
    """Load ``--output-schema`` with ``--output-retries`` for ``run``, or return ``None`` without a schema.

    Raises:
        SchemaError: If the schema file cannot be read or the schema is refused.
        ValueError: If ``--output-retries`` or ``--output-file`` is given without ``--output-schema``.
    """

    if args.output_schema is None:
        for flag, value in (("--output-retries", args.output_retries), ("--output-file", args.output_file)):
            if value is not None:
                raise ValueError(f"{flag} needs --output-schema PATH")
        return None
    retries = DEFAULT_OUTPUT_RETRIES if args.output_retries is None else args.output_retries
    return OutputContract(schema=OutputSchema.load(args.output_schema), retries=retries)


def run_command(args: argparse.Namespace) -> int:
    """Execute the run subcommand.

    A ``--run-id`` the event log already holds is refused before MCP servers or the provider
    start, and nothing is written, so a second run never mixes into a recorded one.

    Args:
        args: Parsed arguments.

    Returns:
        Process exit code.
    """

    try:
        approvals = approval_flag_values(args.require_approval)
        contract = output_contract_from_args(args)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    config = AppConfig.from_env(
        provider=args.provider,
        event_log=args.event_log,
        max_steps=args.max_steps,
        require_approval=approvals,
        usage_limits=usage_limits_from_args(args),
    )
    try:
        check_output_file(args.output_file, config.event_log)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    prices = _price_table(config)
    if prices is None:
        return 2
    if args.run_id and config.event_log.is_file() and _run_recorded(config.event_log, args.run_id):
        print(
            f"error: run {args.run_id} already exists in event log {config.event_log}; "
            "choose a new --run-id (resume continues an interrupted run)",
            file=sys.stderr,
        )
        return 2
    try:
        toolset = start_mcp_toolset(args.mcp_config)
    except (McpConfigError, McpStartupError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    with ExitStack() as cleanup:
        if toolset is not None:
            cleanup.callback(toolset.close)
        tools, safety_policy, tool_specs = build_runtime_tools(config.safety, toolset)
        try:
            check_approval_policy(safety_policy, tools)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        event_log = SQLiteEventLog(config.event_log)
        cleanup.callback(event_log.close)
        runner = AgentRunner(
            provider=build_llm_adapter(config.provider),
            event_log=event_log,
            tools=tools,
            safety_policy=safety_policy,
            tool_specs=tool_specs,
            price_table=prices,
        )
        try:
            result = runner.run(goal=args.goal, run_id=args.run_id, output_contract=contract)
        except RunBusyError as error:
            print(f"error: {error}", file=sys.stderr)
            return EXIT_RUN_BUSY
        return print_result(result, config.event_log, args.output_file)


def approval_flag_values(values: Sequence[str] | None) -> list[str] | None:
    """Return ``--require-approval`` values, or ``None`` when the flag was not given.

    Raises:
        ValueError: If the flag was given without any tool name.
    """

    if values is None:
        return None
    if not parse_approval_patterns(values):
        raise ValueError("--require-approval needs at least one tool name or pattern")
    return list(values)


def check_approval_policy(policy: SafetyPolicy, tools: Mapping[str, ToolAdapter]) -> None:
    """Refuse approval entries that match no registered tool, so a typo never disables a gate.

    Raises:
        ValueError: If an entry matches no registered tool.
    """

    unmatched = sorted(
        pattern for pattern in policy.require_approval if not any(fnmatchcase(name, pattern) for name in tools)
    )
    if unmatched:
        raise ValueError(
            f"require-approval matches no registered tool: {', '.join(unmatched)} "
            "(check --require-approval / MULTIBOT_REQUIRE_APPROVAL; MCP tools need --mcp-config)"
        )


def result_payload(result: RunResult, event_log_path: Path, **extra: Any) -> dict[str, Any]:
    """Return the JSON a run, fork, or resume prints, with the interrupt of a paused run."""

    payload: dict[str, Any] = {
        "run_id": result.run_id,
        **extra,
        "state": result.state.value,
        "answer": result.answer,
        "steps": result.steps,
        "event_log": str(event_log_path),
    }
    if result.output is not None:
        payload["output"] = result.output.value
        payload["output_attempts"] = result.output.attempt
    if result.output_errors:
        payload["output_errors"] = list(result.output_errors)
    if result.usage is not None:
        payload["usage"] = result.usage.to_dict()
    if result.usage_limit is not None:
        payload["usage_limit"] = result.usage_limit.to_dict()
    if result.interrupt is not None:
        record = result.interrupt
        payload["interrupt"] = {
            "interrupt_id": record.interrupt_id,
            "tool": record.tool,
            "step": record.step,
            "bot": record.bot,
            "arguments_preview": record.arguments_preview,
        }
    return payload


def print_result(
    result: RunResult,
    event_log_path: Path,
    output_file: Path | None,
    *,
    resumed: bool | None = None,
    **extra: Any,
) -> int:
    """Write ``--output-file``, print the result JSON and any pause hint, and return the exit code.

    The output file is written only for a validated output; a write error makes the exit code 2
    (the run itself stays recorded as it ended).
    """

    payload = result_payload(result, event_log_path, **extra)
    if resumed is not None:
        payload["resumed"] = resumed
    status = exit_code_for(result)
    if output_file is not None and result.output is not None:
        try:
            write_output_file(output_file, result.output.value)
            payload["output_file"] = str(output_file)
        except OSError as error:
            print(f"error: cannot write output file {output_file}: {error.strerror or error}", file=sys.stderr)
            status = 2
    print(json.dumps(payload, indent=2))
    announce_pause(result, event_log_path)
    if result.state.value == "output_invalid":
        print(
            f"note: run {result.run_id} ended in output_invalid; its answers and validation errors: replay "
            f"--event-log {event_log_path} --run-id {result.run_id} --event-type output_validation_failed",
            file=sys.stderr,
        )
    return status


def announce_pause(result: RunResult, event_log_path: Path) -> None:
    """Tell the operator how to decide a paused run, or how to continue one a usage limit stopped (stderr)."""

    if result.interrupt is not None:
        print_decision_hint(result.interrupt, event_log_path)
    breach = result.usage_limit
    if breach is not None:
        flag = "--" + breach.limit.replace("_", "-")
        if breach.value is None:
            how = f"{flag} cannot be measured for this provider; drop it with --reset-usage-limits"
        else:
            how = f"raise it with {flag} <{'USD' if breach.limit == 'max_cost_usd' else 'N'}>"
        print(f"note: run {result.run_id} stopped at a usage limit: {breach.message}", file=sys.stderr)
        print(
            f"note: continue: resume --run-id {result.run_id} --event-log {event_log_path} and {how}",
            file=sys.stderr,
        )


def _price_table(config: AppConfig) -> PriceTable | None:
    """Load the price table (``MULTIBOT_PRICES_FILE`` on top of the built-in one); print errors."""

    try:
        return config.price_table()
    except PriceTableError as error:
        print(f"error: {error}", file=sys.stderr)
        return None


def print_decision_hint(record: InterruptRecord, event_log_path: Path) -> None:
    """Print where a run paused and the commands that decide and resume it (stderr)."""

    log = event_log_path
    print(
        f"note: run {record.run_id} paused in step {record.step}: {record.tool} needs approval "
        f"(interrupt {record.interrupt_id})",
        file=sys.stderr,
    )
    print(
        f"note: decide: approve|reject {record.interrupt_id} --event-log {log}; "
        f"then: resume --run-id {record.run_id} --event-log {log}",
        file=sys.stderr,
    )


def exit_code_for(result: RunResult) -> int:
    """Return 0 for a succeeded run, 3 for a run paused awaiting approval, 4 for a final answer that
    never validated against its output schema, 5 for a usage-limit stop, else 2."""

    if result.state.value == "succeeded":
        return 0
    if result.state.value == "awaiting_approval":
        return EXIT_AWAITING_APPROVAL
    if result.state.value == "output_invalid":
        return EXIT_OUTPUT_INVALID
    if result.state.value == "usage_limit_exceeded":
        return EXIT_USAGE_LIMIT
    return 2


def _event_log_missing(path: Path) -> bool:
    """Report a missing event log for a command that reads an existing one.

    Opening a ``SQLiteEventLog`` creates a missing file and its parent directories, which only
    commands that write a new log (``run``, ``eval``) should do. Commands that read a log check
    first, so a mistyped ``--event-log`` is an error instead of a new, empty log that looks like
    a run that recorded nothing.

    Args:
        path: Event log path.

    Returns:
        ``True`` after printing an ``error:`` line on stderr when ``path`` is not an existing
        file, otherwise ``False``.
    """

    if path.is_file():
        return False
    print(f"error: event log not found: {path}", file=sys.stderr)
    return True


def replay_command(args: argparse.Namespace) -> int:
    """Execute the replay subcommand.

    Args:
        args: Parsed arguments.

    Returns:
        0, also when ``--event-type`` matches no events; 2 when the event log does not exist or
        ``--run-id`` names a run it doesn't hold.
    """

    if _event_log_missing(args.event_log):
        return 2
    event_log = SQLiteEventLog(args.event_log)
    try:
        events = event_log.list_events(run_id=args.run_id)
        if args.run_id is not None and not events:
            return _report_unknown_run(args.event_log, args.run_id)
        for event in events:
            if args.event_type is not None and event.event_type != args.event_type:
                continue
            print(format_event(event, args.format))
    finally:
        event_log.close()
    return 0


def report_command(args: argparse.Namespace) -> int:
    """Execute the report subcommand.

    Args:
        args: Parsed arguments.

    Returns:
        0 on success, 2 when the event log does not exist or ``--run-id`` names a run it doesn't hold.
    """

    if _event_log_missing(args.event_log):
        return 2
    event_log = SQLiteEventLog(args.event_log)
    try:
        events = event_log.list_events(run_id=args.run_id)
        if args.run_id is not None and not events:
            return _report_unknown_run(args.event_log, args.run_id)
        # Children of a single run can be anywhere in the log: read every run's first event.
        forks = events if args.run_id is None else event_log.list_events()
        print(json.dumps(build_run_report(events, forks=forks), indent=2))
    finally:
        event_log.close()
    return 0


def resume_command(args: argparse.Namespace) -> int:
    """Execute the resume subcommand.

    A missing event log is an error and is never created. A finished run's recorded outcome, an
    unknown run id, or a run paused at an interrupt nobody decided yet is read first, so it is
    reported without starting MCP servers or building the provider.

    Args:
        args: Parsed arguments.

    Returns:
        Process exit code: 0 succeeded, 3 (still) awaiting approval, 4 output invalid, 5 stopped (again)
        at a usage limit, 75 another process is continuing the run (nothing was written), 2 otherwise
        (also when the run is unknown or cannot be resumed).
    """

    try:
        approvals = approval_flag_values(args.require_approval)
        check_output_file(args.output_file, args.event_log)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    config = AppConfig.from_env(
        provider=args.provider,
        event_log=args.event_log,
        max_steps=args.max_steps,
        require_approval=approvals,
        usage_limits=usage_limits_from_args(args),
    )
    if _event_log_missing(config.event_log):
        return 2
    if not _run_recorded(config.event_log, args.run_id):
        return _report_unknown_run(config.event_log, args.run_id)
    if args.output_file is not None and not _has_output_contract(config.event_log, args.run_id):
        print(f"error: run {args.run_id} has no output schema, so --output-file has nothing to write", file=sys.stderr)
        return 2
    try:
        finished = _finished_run_outcome(config.event_log, args.run_id)
    except ResumeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if finished is not None:
        return _print_resume_result(finished, config.event_log, args.output_file)
    waiting = _undecided_interrupt(config.event_log, args.run_id)
    if waiting is not None and not config.safety.is_cancelled():
        return _refuse_undecided(waiting, config.event_log)
    prices = _price_table(config)
    if prices is None:
        return 2
    try:
        toolset = start_mcp_toolset(args.mcp_config)
    except (McpConfigError, McpStartupError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    with ExitStack() as cleanup:
        if toolset is not None:
            cleanup.callback(toolset.close)
        tools, safety_policy, tool_specs = build_runtime_tools(config.safety, toolset)
        try:
            check_approval_policy(safety_policy, tools)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        event_log = SQLiteEventLog(config.event_log)
        cleanup.callback(event_log.close)
        runner = AgentRunner(
            provider=build_llm_adapter(config.provider),
            event_log=event_log,
            tools=tools,
            safety_policy=safety_policy,
            tool_specs=tool_specs,
            price_table=prices,
        )
        try:
            result = runner.resume(run_id=args.run_id, reset_usage_limits=args.reset_usage_limits)
        except RunBusyError as error:
            print(f"error: {error}", file=sys.stderr)
            return EXIT_RUN_BUSY
        except AwaitingApprovalError as error:
            return _refuse_undecided(error.interrupt, config.event_log)
        except (ApprovalError, ResumeError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        return _print_resume_result(result, config.event_log, args.output_file)


def _has_output_contract(path: Path, run_id: str) -> bool:
    """Return whether the run recorded an output contract (an unreadable one counts: resume reports it)."""

    event_log = SQLiteEventLog(path)
    try:
        return recorded_contract(event_log.list_events(run_id)) is not None
    except SchemaError:
        return True
    finally:
        event_log.close()


def _undecided_interrupt(path: Path, run_id: str) -> InterruptRecord | None:
    """Return the undecided interrupt ``run_id`` is paused at, without creating a missing log."""

    if not path.exists():
        return None
    event_log = SQLiteEventLog(path)
    try:
        record = paused_interrupt(event_log.list_events(run_id))
    finally:
        event_log.close()
    return record if record is not None and record.decision is None else None


def _refuse_undecided(record: InterruptRecord, event_log_path: Path) -> int:
    """Explain that a paused run needs a decision first, and return exit code 3."""

    print(
        f"error: run {record.run_id} is awaiting approval of interrupt {record.interrupt_id} "
        f"({record.tool} in step {record.step}); nothing was resumed",
        file=sys.stderr,
    )
    print_decision_hint(record, event_log_path)
    return EXIT_AWAITING_APPROVAL


def _finished_run_outcome(path: Path, run_id: str) -> RunResult | None:
    """Return a finished run's recorded outcome without creating a missing event log.

    Args:
        path: Event log path.
        run_id: Run identifier.

    Returns:
        The recorded outcome, or ``None`` when the run has not finished.
    """

    if not path.exists():
        return None
    event_log = SQLiteEventLog(path)
    try:
        return recorded_outcome(event_log, run_id)
    finally:
        event_log.close()


def _run_recorded(path: Path, run_id: str) -> bool:
    """Return whether the existing event log at ``path`` holds any event of ``run_id``.

    Commands check this before they start MCP servers or build a provider, so a mistyped run id
    is reported as such rather than behind an unrelated startup error or status output.

    Args:
        path: Path of an existing event log.
        run_id: Requested run id.

    Returns:
        ``True`` when the run has at least one event.
    """

    event_log = SQLiteEventLog(path)
    try:
        return bool(event_log.list_events(run_id))
    finally:
        event_log.close()


def _report_unknown_run(path: Path, run_id: str) -> int:
    """Print the one-line error for a run id that has no events in the event log at ``path``.

    The line names the log's most recently active runs, so a mistyped run id is easy to correct.

    Args:
        path: Path of an existing event log.
        run_id: Requested run id.

    Returns:
        Exit code 2.
    """

    event_log = SQLiteEventLog(path)
    try:
        latest = event_log.last_event_timestamps()
    finally:
        event_log.close()
    # The log writes UTC ISO 8601 timestamps, so their string order is their time order.
    runs = sorted(latest, key=lambda run: (latest[run], run), reverse=True)
    if not runs:
        hint = "the log has no runs"
    else:
        hint = "recent runs: " + ", ".join(runs[:RECENT_RUNS_SHOWN])
        if len(runs) > RECENT_RUNS_SHOWN:
            hint += f", and {len(runs) - RECENT_RUNS_SHOWN} more"
    print(f"error: run {run_id} not found in event log {path} ({hint})", file=sys.stderr)
    return 2


def _print_resume_result(result: RunResult, event_log_path: Path, output_file: Path | None = None) -> int:
    """Print a resume result as JSON and return the process exit code.

    Args:
        result: Result of ``AgentRunner.resume`` or a finished run's recorded outcome.
        event_log_path: Event log path echoed in the output.
        output_file: ``--output-file``; a finished run's recorded output is written too.

    Returns:
        0 when the run succeeded, 3 when it paused again awaiting approval, 4 when its final answer
        never validated, 5 when a usage limit stopped it (again), otherwise 2.
    """

    if result.already_finished:
        print(
            f"note: run {result.run_id} already finished ({result.state.value}); nothing to resume",
            file=sys.stderr,
        )
    resumed = not (result.already_finished or result.still_stopped)
    return print_result(result, event_log_path, output_file, resumed=resumed)


def format_event(event: EventRecord, output_format: str) -> str:
    """Format one event for replay output.

    Args:
        event: Event to format.
        output_format: Output format name.

    Returns:
        Formatted event string.
    """

    if output_format == "json":
        return json.dumps(event_to_dict(event), sort_keys=True)
    if output_format == "text":
        return format_event_text(event)
    raise ValueError(f"unsupported output format: {output_format}")


def event_to_dict(event: EventRecord) -> dict[str, Any]:
    """Convert an event record into a JSON-serializable dictionary.

    Args:
        event: Event record.

    Returns:
        Dictionary representation of the event.
    """

    return {
        "run_id": event.run_id,
        "seq": event.seq,
        "timestamp": event.timestamp,
        "event_type": event.event_type,
        "state": event.state,
        "payload": event.payload,
    }


def format_event_text(event: EventRecord) -> str:
    """Format one event as a compact human-readable timeline row.

    Args:
        event: Event record.

    Returns:
        Human-readable event row.
    """

    detail = ""
    if event.event_type == "decision":
        rationale = event.payload.get("rationale", {})
        if isinstance(rationale, dict):
            detail = f" action={event.payload.get('action')} rule={rationale.get('rule_id')}"
    elif event.event_type == "action_result":
        detail = f" kind={event.payload.get('kind')}"
        tool_name = event.payload.get("tool")
        if tool_name is not None:
            detail += f" target={tool_name}"
        metadata = event.payload.get("metadata")
        if isinstance(metadata, dict) and "mcp_server" in metadata:
            ok = str(event.payload.get("ok")).lower()
            detail += f" ok={ok} mcp={metadata['mcp_server']}/{metadata.get('mcp_tool')}"
            if metadata.get("mcp_era"):
                detail += f" era={metadata['mcp_era']}"
    elif event.event_type in {"run_completed", "run_failed", "run_cancelled"}:
        detail = f" result={event.payload}"
    elif event.event_type == RUN_FORKED:
        payload = event.payload
        detail = (
            f" parent={payload.get('parent_run_id')} step={payload.get('fork_step')}"
            f" inherited={payload.get('inherited_events')}"
        )
    elif event.event_type == "interrupt":
        payload = event.payload
        detail = f" id={payload.get('interrupt_id')} tool={payload.get('tool')} step={payload.get('step')}"
    elif event.event_type == "approval_decision":
        payload = event.payload
        detail = (
            f" id={payload.get('interrupt_id')} decision={payload.get('decision')} by={payload.get('decided_by')}"
            f" args_edited={str(payload.get('args_edited') is True).lower()}"
        )
    elif event.event_type == "output_validation_failed":
        payload = event.payload
        errors = payload.get("errors")
        errors = errors if isinstance(errors, list) else []
        detail = (
            f" attempt={payload.get('attempt')}/{payload.get('max_attempts')} errors={len(errors)}"
            f" retry={str(payload.get('retry') is True).lower()}"
        )
        if errors:
            detail += f" first={json.dumps(_clip(str(errors[0]), 100), ensure_ascii=False)}"
    elif event.event_type == "final_output":
        payload = event.payload
        detail = (
            f" attempt={payload.get('attempt')} source={payload.get('source')} bytes={payload.get('bytes')}"
            f" sha256={str(payload.get('output_sha256', ''))[:12]}"
        )
    elif event.event_type == "llm_usage":
        detail = _usage_detail(event.payload)
    elif event.event_type == "usage_limit_exceeded":
        payload = event.payload
        detail = (
            f" limit={payload.get('limit')} value={_number(payload.get('value'))} cap={_number(payload.get('cap'))}"
            f" phase={payload.get('phase')} step={payload.get('step')}"
        )
    return f"{event.seq:03d} {event.state:<10} {event.event_type}{detail}"


def _usage_detail(payload: Mapping[str, Any]) -> str:
    """Summarize an ``llm_usage`` event: provider, model, input/output tokens, and cost."""

    usage = payload.get("usage")
    counts = usage if isinstance(usage, dict) else {}
    cost = payload.get("cost")
    usd = cost.get("usd") if isinstance(cost, dict) else None
    priced = f"${format_number(usd)}" if isinstance(usd, (int, float)) else "unpriced"
    if isinstance(cost, dict) and cost.get("source") == "provider":
        priced += " (provider)"
    tokens = f"{_number(counts.get('input_tokens'))}/{_number(counts.get('output_tokens'))}"
    return f" provider={payload.get('provider')} model={payload.get('model')} tokens_in/out={tokens} cost={priced}"


def _number(value: Any) -> str:
    """Format a recorded counter or USD amount (``unknown`` when missing)."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "unknown"
    return format_number(value)


def build_run_report(events: list[EventRecord], forks: Iterable[EventRecord] = ()) -> dict[str, Any]:
    """Build a structured summary from durable event records.

    A run that was forked, or forked from, also gets a ``lineage`` entry: its ``parent`` (with
    a check that the inherited events still match their recorded digest) and its ``children``.
    Every run gets a ``usage`` entry (its own model calls' tokens and cost, per bot and per model;
    a fork's inherited calls are listed separately), and ``usage_totals`` sums the runs' own calls,
    so a call a fork inherited is counted once.

    Args:
        events: Event records.
        forks: Further events to find children in (only each run's first event is read), for
            reports of a single run.

    Returns:
        Report dictionary grouped by run id.
    """

    lineage_events = {event.run_id: event for event in (*forks, *events) if event.seq == 1}
    children = fork_children(lineage_events.values())
    events_by_run: dict[str, list[EventRecord]] = {}
    reports: dict[str, dict[str, Any]] = {}
    for event in events:
        events_by_run.setdefault(event.run_id, []).append(event)
        report = reports.setdefault(
            event.run_id,
            {
                "run_id": event.run_id,
                "final_state": event.state,
                "event_count": 0,
                "decisions": [],
                "tool_calls": [],
                "answer": None,
            },
        )
        report["final_state"] = event.state
        report["event_count"] += 1
        if event.event_type == "decision":
            rationale = event.payload.get("rationale", {})
            report["decisions"].append(
                {
                    "action": event.payload.get("action"),
                    "target": event.payload.get("target"),
                    "rule_id": rationale.get("rule_id") if isinstance(rationale, dict) else None,
                }
            )
        elif event.event_type == "action_result" and event.payload.get("kind") == "tool":
            report["tool_calls"].append(
                {
                    "tool": event.payload.get("tool"),
                    "ok": event.payload.get("ok"),
                }
            )
        elif event.event_type == "run_completed":
            report["answer"] = event.payload.get("answer")
    for record in collect_interrupts(events):
        reports[record.run_id].setdefault("interrupts", []).append(record.to_dict())
    own_usage = UsageTotals()
    for run_id, report in reports.items():
        run_events = events_by_run[run_id]
        output = output_report(run_events)
        if output is not None:
            report["output"] = output
        lineage = parse_lineage(min(run_events, key=lambda item: item.seq))
        # A fork's inherited copies follow its run_forked event (seq 1); their calls belong to the parent.
        inherited_through = 1 + lineage.inherited_events if lineage is not None else 0
        report["usage"] = usage_summary(run_events, inherited_through_seq=inherited_through)
        own_usage = own_usage.merge(
            UsageTotals.from_events(event for event in run_events if event.seq > inherited_through)
        )
        forked = children.get(run_id, [])
        if lineage is None and not forked:
            continue
        parent = None
        if lineage is not None:
            parent = lineage.summary() | {"inherited_events_verified": inherited_events_intact(run_events, lineage)}
        report["lineage"] = {
            "parent": parent,
            "children": [
                {"run_id": child.run_id, "fork_step": child.fork_step, "overrides": dict(child.overrides)}
                for child in forked
            ],
        }
    return {"runs": list(reports.values()), "usage_totals": own_usage.to_dict()}


def output_report(events: Sequence[EventRecord]) -> dict[str, Any] | None:
    """Summarize a run's output contract and its validated output or last validation errors.

    Args:
        events: Events of one run.

    Returns:
        ``None`` for a run without an output schema; otherwise its schema digest and source, the
        correction-round budget, the answers checked against that schema (inherited ones included),
        ``valid`` (``null`` before the first check), and the output or the errors of the last
        invalid answer.
    """

    try:
        contract = recorded_contract(events)
    except SchemaError as error:
        return {"error": str(error)}
    if contract is None:
        return None
    # A fork's inherited checks against a schema it replaced are not answers to this contract.
    output, errors = recorded_output(events, schema_sha256=contract.schema.sha256)
    failures = failed_attempts(events, contract.schema.sha256)
    report: dict[str, Any] = {
        "schema_sha256": contract.schema.sha256,
        "schema_source": contract.schema.source,
        "retries": contract.retries,
        "attempts": failures + (1 if output is not None else 0),
        "valid": True if output is not None else (False if failures else None),
    }
    if output is not None:
        report["value"] = output.value
        report["output_sha256"] = output.output_sha256
    elif errors:
        report["errors"] = list(errors)
    return report


def history_command(args: argparse.Namespace) -> int:
    """Execute the history subcommand: list a run's steps and which ones can be forked.

    Reads the event log only; never calls a provider or tool.

    Args:
        args: Parsed arguments.

    Returns:
        0 on success, 2 for a missing or unreadable log or an unknown run.
    """

    from multi_bot_agentic.tracing import select_latest_run

    path: Path = args.event_log
    if _event_log_missing(path):
        return 2
    try:
        event_log = SQLiteEventLog(path)
        try:
            run_id = args.run_id or select_latest_run(event_log.last_event_timestamps())
            events = event_log.list_events(run_id=run_id) if run_id is not None else []
        finally:
            event_log.close()
    except sqlite3.DatabaseError as error:
        print(f"error: cannot read event log {path}: {error}", file=sys.stderr)
        return 2
    if run_id is None:
        print(f"error: event log {path} has no runs", file=sys.stderr)
        return 2
    if not events:
        return _report_unknown_run(path, run_id)
    if args.run_id is None:
        print(f"note: --run-id not given; showing the most recent run {run_id}", file=sys.stderr)
    history = build_history(events)
    if args.format == "json":
        print(json.dumps(history.to_dict(), indent=2))
    else:
        print(format_history_text(history))
    return 0


def format_history_text(history: RunHistory) -> str:
    """Format a run's steps as a table; ``*`` marks steps inherited from the parent run.

    Args:
        history: Run history.

    Returns:
        Multi-line text.
    """

    status = f"{history.final_state} after {_quantity(history.last_step, 'step')}"
    if history.final_state == "awaiting_approval":
        status = f"paused in step {history.last_step}, awaiting human approval"
    elif history.final_state == "usage_limit_exceeded":
        status = f"stopped at a usage limit after {_quantity(history.last_step, 'step')} (resume with a higher limit)"
    lines = [f"run {history.run_id}: {status} (provider {history.provider or 'unknown'})"]
    lineage = history.lineage
    if lineage is not None:
        changed = f" (new {', '.join(sorted(lineage.overrides))})" if lineage.overrides else ""
        lines.append(f"forked from {lineage.parent_run_id} after step {lineage.fork_step}{changed}; * = inherited")
    if history.goal is not None:
        lines.append(f"goal: {history.goal}")
    header = ("step", "bot", "action", "target", "rule", "outcome", "fork")
    rows = [
        (
            f"{item.step}{'*' if item.inherited else ''}",
            item.bot or "-",
            item.action or "start",
            item.target or "-",
            item.rule_id or "-",
            item.outcome if item.step else "-",
            "yes" if item.forkable else "no",
        )
        for item in history.steps
    ]
    widths = [max(len(row[column]) for row in (header, *rows)) for column in range(len(header))]
    for row in (header, *rows):
        cells = [row[0].rjust(widths[0])] + [cell.ljust(width) for cell, width in zip(row[1:], widths[1:], strict=True)]
        lines.append("  ".join(cells).rstrip())
    forkable = ", ".join(str(step) for step in history.forkable_steps()) or "none"
    lines.append(f"forkable steps: {forkable}")
    return "\n".join(lines)


def _quantity(number: int, noun: str) -> str:
    """Return ``"<n> <noun>"`` with a plural ``s`` when ``n != 1``."""

    return f"{number} {noun}{'' if number == 1 else 's'}"


def fork_command(args: argparse.Namespace) -> int:
    """Execute the fork subcommand: branch a recorded run after a step and continue it.

    Every check runs before anything is written, and the provider is built (never called)
    before the fork starts, so a missing API key fails without leaving a half-written fork.
    ``--dry-run`` prints the rebuilt state and the first decision instead.

    Args:
        args: Parsed arguments.

    Returns:
        0 when the fork succeeded (or the dry run passed), 3 when it paused awaiting approval, 4 when
        its final answer never validated, 5 when a usage limit stopped it, otherwise 2.
    """

    path: Path = args.event_log
    if _event_log_missing(path):
        return 2
    if not _run_recorded(path, args.run_id):
        return _report_unknown_run(path, args.run_id)
    if args.bot is not None and args.bots is None:
        print("error: --bot needs --bots PATH, the registry that defines the bot's tool scope", file=sys.stderr)
        return 2
    try:
        config = AppConfig.from_env(
            provider=args.provider,
            event_log=path,
            max_steps=args.max_steps,
            require_approval=approval_flag_values(args.require_approval),
            usage_limits=usage_limits_from_args(args),
        )
        bots: dict[str, BotSpec] = load_bot_registry(args.bots) if args.bots is not None else {}
        check_output_file(args.output_file, path)
        output_schema = OutputSchema.load(args.output_schema) if args.output_schema is not None else None
        prices = config.price_table()
    except (BotRegistryError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    try:
        toolset = start_mcp_toolset(args.mcp_config)
    except (McpConfigError, McpStartupError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    with ExitStack() as cleanup:
        if toolset is not None:
            cleanup.callback(toolset.close)
        event_log = SQLiteEventLog(path)
        cleanup.callback(event_log.close)
        tools, safety_policy, tool_specs = build_runtime_tools(config.safety, toolset)
        try:
            check_approval_policy(safety_policy, tools)
            plan = plan_fork(
                event_log,
                args.run_id,
                args.at_step,
                args.new_run_id,
                provider=config.provider,
                policy=safety_policy,
                bots=bots,
                goal=args.goal,
                bot_id=args.bot,
                output_schema=output_schema,
                output_retries=args.output_retries,
            )
            if args.output_file is not None and plan.output_contract is None:
                raise ValueError(f"run {args.run_id} has no output schema, so --output-file needs --output-schema PATH")
            provider = build_llm_adapter(config.provider)
        except (ForkError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if args.dry_run:
            dry_run = plan.to_dict()
            inherited, limits = fork_usage(plan, safety_policy.usage_limits, reset=args.reset_usage_limits)
            if inherited.requests or limits.active:
                dry_run["usage"] = {"inherited": inherited.to_dict(), "limits": limits.to_dict()}
            print(json.dumps(dry_run, indent=2))
            return 0
        runner = AgentRunner(
            provider=provider,
            event_log=event_log,
            tools=tools,
            safety_policy=safety_policy,
            bots=bots,
            tool_specs=tool_specs,
            price_table=prices,
        )
        try:
            result = runner.fork(
                args.run_id,
                args.at_step,
                args.new_run_id,
                goal=args.goal,
                bot_id=args.bot,
                output_schema=output_schema,
                output_retries=args.output_retries,
                reset_usage_limits=args.reset_usage_limits,
            )
        except RunBusyError as error:
            print(f"error: {error}", file=sys.stderr)
            return EXIT_RUN_BUSY
        overrides = plan.lineage.get("overrides", {})
        changed = f"; new {', '.join(sorted(overrides))}" if overrides else ""
        print(
            f"note: forked run {args.run_id} after step {args.at_step} into {result.run_id} "
            f"({_quantity(len(plan.point.prefix), 'event')} inherited{changed})",
            file=sys.stderr,
        )
        return print_result(result, path, args.output_file, parent_run_id=args.run_id, fork_step=args.at_step)


def approvals_command(args: argparse.Namespace) -> int:
    """Execute ``approvals list`` and ``approvals show``: read-only views of interrupts.

    Args:
        args: Parsed arguments.

    Returns:
        0 on success, 2 for a missing or unreadable log, an unknown run, or an unknown interrupt.
    """

    path: Path = args.event_log
    if _event_log_missing(path):
        return 2
    try:
        event_log = SQLiteEventLog(path)
        try:
            if args.approvals_command == "show":
                record = find_interrupt(event_log, args.interrupt_id, run_id=args.run_id)
                print(format_interrupt(record, args.format, path))
                return 0
            events = event_log.list_events(run_id=args.run_id)
        finally:
            event_log.close()
    except sqlite3.DatabaseError as error:
        print(f"error: cannot read event log {path}: {error}", file=sys.stderr)
        return 2
    except ApprovalError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.run_id is not None and not events:
        return _report_unknown_run(path, args.run_id)
    records = [record for record in collect_interrupts(events) if args.all or record.status == "pending"]
    if args.format == "json":
        print(json.dumps([record.to_dict() for record in records], indent=2))
    elif not records:
        print(f"no {'' if args.all else 'pending '}interrupts in {path}")
    else:
        print(format_interrupt_table(records))
    return 0


def format_interrupt_table(records: Sequence[InterruptRecord]) -> str:
    """Format interrupts as a table, one per line."""

    header = ("interrupt", "run", "step", "tool", "bot", "status", "decided by", "arguments")
    rows = [
        (
            record.interrupt_id,
            record.run_id,
            str(record.step),
            record.tool,
            record.bot or "-",
            record.status,
            record.decision.decided_by if record.decision is not None else "-",
            _clip(_effective_preview(record), 48),
        )
        for record in records
    ]
    widths = [max(len(row[column]) for row in (header, *rows)) for column in range(len(header))]
    lines = []
    for row in (header, *rows):
        cells = [
            cell.rjust(width) if column == 2 else cell.ljust(width)
            for column, (cell, width) in enumerate(zip(row, widths, strict=True))
        ]
        lines.append("  ".join(cells).rstrip())
    return "\n".join(lines)


def format_interrupt(record: InterruptRecord, output_format: str, event_log_path: Path) -> str:
    """Format one interrupt with its complete, redacted arguments (no length cap) and decision."""

    from multi_bot_agentic.tracing.privacy import redact_value

    details = record.to_dict()
    details["arguments"] = redact_value(dict(record.arguments), limit=None)
    if record.decision is not None and record.decision.arguments is not None:
        details["decision"]["arguments"] = redact_value(dict(record.decision.arguments), limit=None)
    details["explanation"] = record.explanation
    if output_format == "json":
        return json.dumps(details, indent=2)
    lines = [
        f"interrupt {record.interrupt_id}: {record.status}",
        f"  run:        {record.run_id} (step {record.step}{', bot ' + record.bot if record.bot else ''})",
        f"  tool:       {record.tool}",
        f"  arguments:  {json.dumps(details['arguments'], sort_keys=True, ensure_ascii=False)}",
        f"  requested:  {record.requested_at}",
        f"  why:        {record.rule_id}: {record.explanation}",
    ]
    decision = record.decision
    if decision is None and record.paused:
        lines.append(
            f"  decide:     approve {record.interrupt_id} --event-log {event_log_path} [--args JSON] | "
            f"reject {record.interrupt_id} --event-log {event_log_path} --reason TEXT"
        )
    elif decision is not None:
        lines.append(f"  decision:   {decision.decision.value} by {decision.decided_by} at {decision.decided_at}")
        if decision.reason:
            lines.append(f"  reason:     {decision.reason}")
        if decision.arguments is not None:
            edited = json.dumps(details["decision"]["arguments"], sort_keys=True, ensure_ascii=False)
            lines.append(f"  edited to:  {edited}")
        state = "executed" if record.executed else ("resumed" if not record.paused else "waiting for resume")
        lines.append(f"  progress:   {state}")
    return "\n".join(lines)


def decide_command(args: argparse.Namespace, decision: ApprovalDecision) -> int:
    """Execute ``approve`` or ``reject``: record a human decision on a paused run's interrupt.

    Nothing runs here; ``resume`` acts on the decision.

    Args:
        args: Parsed arguments.
        decision: ``APPROVED`` or ``REJECTED``.

    Returns:
        0 when the decision was recorded, 2 otherwise (nothing was written).
    """

    path: Path = args.event_log
    if _event_log_missing(path):
        return 2
    if args.interrupt_id is None and args.run_id is None:
        print("error: give an interrupt id, or --run-id to decide the interrupt that run is paused at", file=sys.stderr)
        return 2
    arguments: Any = None
    raw_arguments = getattr(args, "args", None)
    if raw_arguments is not None:
        try:
            arguments = json.loads(raw_arguments)
        except ValueError as error:
            print(f"error: --args is not valid JSON: {error}", file=sys.stderr)
            return 2
        if arguments is None:
            # decide_interrupt reads None as "keep the arguments"; an explicit null is not an edit.
            print("error: --args must be a JSON object, got null (omit --args to keep the arguments)", file=sys.stderr)
            return 2
    try:
        event_log = SQLiteEventLog(path)
        try:
            record = decide_interrupt(
                event_log,
                args.interrupt_id,
                decision,
                decided_by=args.by if args.by is not None else default_approver(),
                reason=args.reason,
                arguments=arguments,
                run_id=args.run_id,
            )
        finally:
            event_log.close()
    except sqlite3.DatabaseError as error:
        print(f"error: cannot read event log {path}: {error}", file=sys.stderr)
        return 2
    except ApprovalError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(record.to_dict(), indent=2))
    print(
        f"note: {decision.value} interrupt {record.interrupt_id}; "
        f"continue the run with 'resume --run-id {record.run_id} --event-log {path}'",
        file=sys.stderr,
    )
    return 0


def default_approver() -> str:
    """Return the OS user name, or ``unknown``."""

    try:
        return getpass.getuser() or "unknown"
    except (KeyError, OSError, ImportError):
        return "unknown"


def _effective_preview(record: InterruptRecord) -> str:
    """Return the preview of the arguments an approved call runs with, marking edits."""

    decision = record.decision
    if decision is not None and decision.arguments_preview is not None:
        return f"(edited) {decision.arguments_preview}"
    return record.arguments_preview


def _clip(text: str, limit: int) -> str:
    """Shorten ``text`` to ``limit`` characters with an ellipsis."""

    return text if len(text) <= limit else text[: limit - 3] + "..."


def eval_command(args: argparse.Namespace) -> int:
    """Execute the eval subcommand.

    Args:
        args: Parsed arguments.

    Returns:
        Process exit code.
    """

    from multi_bot_agentic.eval import EvaluationHarness, default_fixture_dir, load_scenarios

    fixture_dir = args.fixtures or default_fixture_dir()
    try:
        scenarios = load_scenarios(fixture_dir)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    report = EvaluationHarness(scenarios).run(root=Path.cwd(), event_log_dir=args.event_log_dir)
    print(
        json.dumps(
            {
                "pass_rate": report.pass_rate,
                "mean_tool_sequence_score": report.mean_tool_sequence_score,
                "mean_answer_score": report.mean_answer_score,
                "mean_output_score": report.mean_output_score,
                "usage_totals": report.usage_totals.to_dict(),
                "scenarios": [
                    {
                        "scenario_id": item.scenario_id,
                        "passed": item.passed,
                        "tool_sequence_score": item.tool_sequence_score,
                        "answer_score": item.answer_score,
                        "output_score": item.output_score,
                        "actual_tools": list(item.actual_tools),
                        "actual_answer": item.actual_answer,
                        **({"actual_output": item.actual_output} if item.actual_output is not None else {}),
                        "details": item.details,
                    }
                    for item in report.scenarios
                ],
            },
            indent=2,
        )
    )
    return 0 if report.pass_rate == 1.0 else 2


def trace_command(args: argparse.Namespace) -> int:
    """Execute the trace subcommand.

    Reads one run from the event log (never calling a provider or tool), renders it as
    OTLP/JSON or Mermaid, and optionally pushes the OTLP/JSON to an OTLP/HTTP endpoint.

    Args:
        args: Parsed arguments.

    Returns:
        0 on success, 2 for invalid arguments, a missing log, or an unknown run, and 1 when
        the OTLP/HTTP export fails.
    """

    from multi_bot_agentic.tracing import (
        OtlpExportError,
        OtlpHeaderError,
        TraceInputError,
        build_trace,
        parse_header_options,
        push_otlp_json,
        redact_url,
        render_mermaid,
        render_otlp_json,
        select_latest_run,
        validate_endpoint,
    )

    try:
        headers = parse_header_options(args.otlp_header)
        if args.otlp_endpoint is not None:
            validate_endpoint(args.otlp_endpoint)
        elif headers:
            raise ValueError("--otlp-header requires --otlp-endpoint")
        if args.otlp_timeout <= 0:
            raise ValueError("--otlp-timeout must be > 0")
    except (OtlpHeaderError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    path: Path = args.event_log
    if _event_log_missing(path):
        return 2
    try:
        event_log = SQLiteEventLog(path)
        try:
            run_id = args.run_id or select_latest_run(event_log.last_event_timestamps())
            events = event_log.list_events(run_id=run_id) if run_id is not None else []
        finally:
            event_log.close()
    except sqlite3.DatabaseError as error:
        print(f"error: cannot read event log {path}: {error}", file=sys.stderr)
        return 2
    if run_id is None:
        print(f"error: event log {path} has no runs", file=sys.stderr)
        return 2
    if not events:
        return _report_unknown_run(path, run_id)
    if args.run_id is None:
        print(f"note: --run-id not given; tracing the most recent run {run_id}", file=sys.stderr)
    try:
        trace = build_trace(events, include_content=args.include_content, agent_name=args.agent_name)
        output_format = args.format
        if output_format is None and (args.otlp_endpoint is None or args.output is not None):
            output_format = "otlp-json"
        if output_format == "mermaid":
            rendered = render_mermaid(events, include_content=args.include_content, agent_name=args.agent_name)
        elif output_format == "otlp-json":
            rendered = render_otlp_json(trace)
        else:
            rendered = None
    except TraceInputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if rendered is not None:
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
            print(f"wrote {output_format} trace of run {run_id} to {args.output}", file=sys.stderr)
        else:
            print(rendered)
    if args.otlp_endpoint is None:
        return 0
    try:
        result = push_otlp_json(
            render_otlp_json(trace, indent=None).encode("utf-8"),
            args.otlp_endpoint,
            headers=headers,
            timeout_seconds=args.otlp_timeout,
        )
    except OtlpExportError as error:
        print(f"error: OTLP export failed: {error}", file=sys.stderr)
        return 1
    print(
        f"exported {_count(tuple(span.name for span in trace.spans), 'span')} of run {run_id} "
        f"(trace {trace.trace_id}) to {redact_url(args.otlp_endpoint)}: HTTP {result.status}",
        file=sys.stderr,
    )
    if result.rejected_spans:
        reason = result.message or "no reason given"
        print(f"warning: the OTLP receiver rejected {result.rejected_spans} span(s): {reason}", file=sys.stderr)
    elif result.message:
        print(f"warning: the OTLP receiver said: {result.message}", file=sys.stderr)
    return 0


def start_mcp_toolset(path: Path | None) -> McpToolset | None:
    """Start the MCP servers in ``path`` for a run, failing fast on any startup error.

    Args:
        path: Optional MCP config path from ``--mcp-config``.

    Returns:
        Started toolset, or ``None`` when no config was given.

    Raises:
        McpConfigError: If the config file is invalid.
        McpStartupError: If any enabled server cannot be started or listed.
    """

    if path is None:
        return None
    config = load_mcp_config(path)
    for warning in config.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    toolset = McpToolset(config)
    try:
        statuses = toolset.start()
    except BaseException:
        toolset.close()
        raise
    if toolset.failed:
        toolset.close()
        details = "; ".join(f"{status.name}: {status.error}" for status in toolset.failed)
        raise McpStartupError(f"MCP server startup failed: {details}")
    for status in statuses:
        if not status.disabled:
            print(
                f"mcp: {status.name} {status.era} {status.protocol_version} ({_count(status.tools, 'tool')})",
                file=sys.stderr,
            )
    return toolset


def build_runtime_tools(
    policy: SafetyPolicy,
    toolset: McpToolset | None,
) -> tuple[dict[str, ToolAdapter], SafetyPolicy, tuple[ToolSpec, ...]]:
    """Merge built-in tools with MCP tools and allowlist the MCP tools for the run.

    Args:
        policy: Safety policy from configuration.
        toolset: Started MCP toolset, if any.

    Returns:
        Tool registry, safety policy, and the MCP tool catalog advertised to the model.

    Raises:
        ValueError: If an MCP tool name collides with a registered tool.
    """

    tools = build_default_tools(root=Path.cwd())
    if toolset is None:
        return tools, policy, ()
    mcp_tools = toolset.tools
    collisions = sorted(set(tools) & set(mcp_tools))
    if collisions:
        raise ValueError(f"MCP tool names collide with built-in tools: {', '.join(collisions)}")
    tools.update(mcp_tools)
    allowed = policy.allowed_tools | frozenset(mcp_tools)
    return tools, replace(policy, allowed_tools=allowed), toolset.specs()


def _count(items: tuple[str, ...], noun: str) -> str:
    """Return ``"<n> <noun>"`` with a plural ``s`` when ``n != 1``."""

    return f"{len(items)} {noun}{'' if len(items) == 1 else 's'}"


def mcp_tools_command(args: argparse.Namespace) -> int:
    """Execute the mcp-tools subcommand.

    Args:
        args: Parsed arguments.

    Returns:
        Process exit code (1 when any server failed, 2 for an invalid config).
    """

    try:
        config = load_mcp_config(args.mcp_config)
    except McpConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    for warning in config.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    with McpToolset(config) as toolset:
        statuses = toolset.start()
        tools = toolset.tools
        if args.format == "json":
            payload = {
                "servers": [mcp_status_to_dict(status) for status in statuses],
                "tools": [
                    {
                        "name": adapter.name,
                        "server": adapter.server_name,
                        "remote_name": adapter.remote_name,
                        "description": adapter.description,
                        "input_schema": adapter.input_schema,
                    }
                    for adapter in tools.values()
                ],
            }
            print(json.dumps(payload, indent=2))
        else:
            print(format_mcp_listing(statuses, {name: adapter.spec() for name, adapter in tools.items()}))
    return 1 if any(status.error for status in statuses) else 0


def mcp_status_to_dict(status: McpServerStatus) -> dict[str, Any]:
    """Convert a server status into a JSON-serializable dictionary.

    Args:
        status: Server startup outcome.

    Returns:
        Dictionary representation.
    """

    return {
        "name": status.name,
        "era": status.era,
        "protocol_version": status.protocol_version,
        "server_info": dict(status.server_info or {}),
        "tools": list(status.tools),
        "hidden_tools": list(status.hidden_tools),
        "skipped_tools": list(status.skipped_tools),
        "error": status.error,
        "disabled": status.disabled,
    }


def format_mcp_listing(statuses: tuple[McpServerStatus, ...], specs: dict[str, ToolSpec]) -> str:
    """Format MCP servers and their exposed tools for terminal output.

    Args:
        statuses: Per-server startup outcomes.
        specs: Exposed tool specs keyed by namespaced name.

    Returns:
        Multi-line listing.
    """

    lines: list[str] = []
    for status in statuses:
        if status.disabled:
            lines.append(f"server {status.name}: disabled")
            continue
        if status.error is not None:
            lines.append(f"server {status.name}: ERROR {status.error}")
            continue
        info = status.server_info or {}
        identity = f"{info.get('name', '?')}/{info.get('version', '?')}"
        summary = f"server {status.name}: {status.era} {status.protocol_version} ({identity})"
        summary += f", {_count(status.tools, 'tool')}"
        if status.hidden_tools:
            summary += f", {len(status.hidden_tools)} hidden by allow/deny lists"
        if status.skipped_tools:
            summary += f", skipped: {', '.join(status.skipped_tools)}"
        lines.append(summary)
        for name in status.tools:
            spec = specs[name]
            description = spec.description if len(spec.description) <= 88 else spec.description[:87].rstrip() + "…"
            lines.append(f"  - {name}({spec.signature()})")
            lines.append(f"      {description}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
