"""Command-line interface for multi-bot-agentic."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Iterable
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from typing import Any

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
from multi_bot_agentic.runner import AgentRunner, RunResult, build_default_tools, recorded_outcome
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.base import ToolAdapter

MCP_CONFIG_HELP = "MCP servers JSON (Claude Desktop 'mcpServers' format); tools appear as mcp__<server>__<tool>"
BOTS_HELP = 'bot registry JSON: {"bots": {"<id>": {"allowed_tools": [...], "name": "...", "description": "..."}}}'
TRACE_FORMATS = ("otlp-json", "mermaid")


class McpStartupError(RuntimeError):
    """Raised when a configured MCP server cannot be started for a run."""


def main() -> int:
    """Run the CLI.

    Returns:
        Process exit code.
    """

    parser = build_parser()
    args = parser.parse_args()
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
    return parser


def _step_number(value: str) -> int:
    """Parse a ``--at-step`` value: an integer >= 0."""

    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be an integer >= 0, got {value!r}") from None
    if number < 0:
        raise argparse.ArgumentTypeError(f"must be an integer >= 0, got {value!r}")
    return number


def run_command(args: argparse.Namespace) -> int:
    """Execute the run subcommand.

    Args:
        args: Parsed arguments.

    Returns:
        Process exit code.
    """

    config = AppConfig.from_env(
        provider=args.provider,
        event_log=args.event_log,
        max_steps=args.max_steps,
    )
    try:
        toolset = start_mcp_toolset(args.mcp_config)
    except (McpConfigError, McpStartupError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    with ExitStack() as cleanup:
        if toolset is not None:
            cleanup.callback(toolset.close)
        event_log = SQLiteEventLog(config.event_log)
        cleanup.callback(event_log.close)
        tools, safety_policy, tool_specs = build_runtime_tools(config.safety, toolset)
        runner = AgentRunner(
            provider=build_llm_adapter(config.provider),
            event_log=event_log,
            tools=tools,
            safety_policy=safety_policy,
            tool_specs=tool_specs,
        )
        result = runner.run(goal=args.goal, run_id=args.run_id)
        print(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "state": result.state.value,
                    "answer": result.answer,
                    "steps": result.steps,
                    "event_log": str(config.event_log),
                },
                indent=2,
            )
        )
        return 0 if result.state.value == "succeeded" else 2


def replay_command(args: argparse.Namespace) -> int:
    """Execute the replay subcommand.

    Args:
        args: Parsed arguments.

    Returns:
        Process exit code.
    """

    event_log = SQLiteEventLog(args.event_log)
    try:
        for event in event_log.list_events(run_id=args.run_id):
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
        Process exit code.
    """

    event_log = SQLiteEventLog(args.event_log)
    try:
        events = event_log.list_events(run_id=args.run_id)
        # Children of a single run can be anywhere in the log: read every run's first event.
        forks = events if args.run_id is None else event_log.list_events()
        print(json.dumps(build_run_report(events, forks=forks), indent=2))
    finally:
        event_log.close()
    return 0


def resume_command(args: argparse.Namespace) -> int:
    """Execute the resume subcommand.

    A finished run's recorded outcome is read first, so it is reported without starting
    MCP servers or building the provider.

    Args:
        args: Parsed arguments.

    Returns:
        Process exit code.
    """

    config = AppConfig.from_env(
        provider=args.provider,
        event_log=args.event_log,
        max_steps=args.max_steps,
    )
    finished = _finished_run_outcome(config.event_log, args.run_id)
    if finished is not None:
        return _print_resume_result(finished, config.event_log)
    try:
        toolset = start_mcp_toolset(args.mcp_config)
    except (McpConfigError, McpStartupError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    with ExitStack() as cleanup:
        if toolset is not None:
            cleanup.callback(toolset.close)
        event_log = SQLiteEventLog(config.event_log)
        cleanup.callback(event_log.close)
        tools, safety_policy, tool_specs = build_runtime_tools(config.safety, toolset)
        runner = AgentRunner(
            provider=build_llm_adapter(config.provider),
            event_log=event_log,
            tools=tools,
            safety_policy=safety_policy,
            tool_specs=tool_specs,
        )
        return _print_resume_result(runner.resume(run_id=args.run_id), config.event_log)


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


def _print_resume_result(result: RunResult, event_log_path: Path) -> int:
    """Print a resume result as JSON and return the process exit code.

    Args:
        result: Result of ``AgentRunner.resume`` or a finished run's recorded outcome.
        event_log_path: Event log path echoed in the output.

    Returns:
        0 when the run succeeded, otherwise 2.
    """

    if result.already_finished:
        print(
            f"note: run {result.run_id} already finished ({result.state.value}); nothing to resume",
            file=sys.stderr,
        )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "state": result.state.value,
                "answer": result.answer,
                "steps": result.steps,
                "event_log": str(event_log_path),
                "resumed": not result.already_finished,
            },
            indent=2,
        )
    )
    return 0 if result.state.value == "succeeded" else 2


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
    return f"{event.seq:03d} {event.state:<10} {event.event_type}{detail}"


def build_run_report(events: list[EventRecord], forks: Iterable[EventRecord] = ()) -> dict[str, Any]:
    """Build a structured summary from durable event records.

    A run that was forked, or forked from, also gets a ``lineage`` entry: its ``parent`` (with
    a check that the inherited events still match their recorded digest) and its ``children``.

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
    for run_id, report in reports.items():
        run_events = events_by_run[run_id]
        lineage = parse_lineage(min(run_events, key=lambda item: item.seq))
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
    return {"runs": list(reports.values())}


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
    if not path.is_file():
        print(f"error: event log not found: {path}", file=sys.stderr)
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
        print(f"error: run {run_id} not found in event log {path}", file=sys.stderr)
        return 2
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
        0 when the fork succeeded (or the dry run passed), otherwise 2.
    """

    path: Path = args.event_log
    if not path.is_file():
        print(f"error: event log not found: {path}", file=sys.stderr)
        return 2
    if args.bot is not None and args.bots is None:
        print("error: --bot needs --bots PATH, the registry that defines the bot's tool scope", file=sys.stderr)
        return 2
    try:
        config = AppConfig.from_env(provider=args.provider, event_log=path, max_steps=args.max_steps)
        bots: dict[str, BotSpec] = load_bot_registry(args.bots) if args.bots is not None else {}
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
            )
            provider = build_llm_adapter(config.provider)
        except (ForkError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if args.dry_run:
            print(json.dumps(plan.to_dict(), indent=2))
            return 0
        runner = AgentRunner(
            provider=provider,
            event_log=event_log,
            tools=tools,
            safety_policy=safety_policy,
            bots=bots,
            tool_specs=tool_specs,
        )
        result = runner.fork(args.run_id, args.at_step, args.new_run_id, goal=args.goal, bot_id=args.bot)
        overrides = plan.lineage.get("overrides", {})
        changed = f"; new {', '.join(sorted(overrides))}" if overrides else ""
        print(
            f"note: forked run {args.run_id} after step {args.at_step} into {result.run_id} "
            f"({_quantity(len(plan.point.prefix), 'event')} inherited{changed})",
            file=sys.stderr,
        )
        print(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "parent_run_id": args.run_id,
                    "fork_step": args.at_step,
                    "state": result.state.value,
                    "answer": result.answer,
                    "steps": result.steps,
                    "event_log": str(path),
                },
                indent=2,
            )
        )
        return 0 if result.state.value == "succeeded" else 2


def eval_command(args: argparse.Namespace) -> int:
    """Execute the eval subcommand.

    Args:
        args: Parsed arguments.

    Returns:
        Process exit code.
    """

    from multi_bot_agentic.eval import EvaluationHarness, default_fixture_dir, load_scenarios

    fixture_dir = args.fixtures or default_fixture_dir()
    scenarios = load_scenarios(fixture_dir)
    report = EvaluationHarness(scenarios).run(root=Path.cwd(), event_log_dir=args.event_log_dir)
    print(
        json.dumps(
            {
                "pass_rate": report.pass_rate,
                "mean_tool_sequence_score": report.mean_tool_sequence_score,
                "mean_answer_score": report.mean_answer_score,
                "scenarios": [
                    {
                        "scenario_id": item.scenario_id,
                        "passed": item.passed,
                        "tool_sequence_score": item.tool_sequence_score,
                        "answer_score": item.answer_score,
                        "actual_tools": list(item.actual_tools),
                        "actual_answer": item.actual_answer,
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
    if not path.is_file():
        print(f"error: event log not found: {path}", file=sys.stderr)
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
        print(f"error: run {run_id} not found in event log {path}", file=sys.stderr)
        return 2
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
