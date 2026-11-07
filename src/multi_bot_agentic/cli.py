"""Command-line interface for multi-bot-agentic."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from typing import Any

from multi_bot_agentic.config import AppConfig, build_llm_adapter
from multi_bot_agentic.event_log import EventRecord, SQLiteEventLog
from multi_bot_agentic.mcp import McpConfigError, McpServerStatus, McpToolset, load_mcp_config
from multi_bot_agentic.models import ToolSpec
from multi_bot_agentic.runner import AgentRunner, RunResult, build_default_tools, recorded_outcome
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.base import ToolAdapter

MCP_CONFIG_HELP = "MCP servers JSON (Claude Desktop 'mcpServers' format); tools appear as mcp__<server>__<tool>"


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
    return parser


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
        print(json.dumps(build_run_report(event_log.list_events(run_id=args.run_id)), indent=2))
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
    return f"{event.seq:03d} {event.state:<10} {event.event_type}{detail}"


def build_run_report(events: list[EventRecord]) -> dict[str, Any]:
    """Build a structured summary from durable event records.

    Args:
        events: Event records.

    Returns:
        Report dictionary grouped by run id.
    """

    reports: dict[str, dict[str, Any]] = {}
    for event in events:
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
    return {"runs": list(reports.values())}


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
