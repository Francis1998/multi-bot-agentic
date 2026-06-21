"""Command-line interface for multi-bot-agentic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from multi_bot_agentic.config import AppConfig, build_llm_adapter
from multi_bot_agentic.event_log import EventRecord, SQLiteEventLog
from multi_bot_agentic.runner import AgentRunner, build_default_tools


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

    replay_parser = subparsers.add_parser("replay", help="print durable event log")
    replay_parser.add_argument("--event-log", type=Path, required=True, help="sqlite event log path")
    replay_parser.add_argument("--run-id", default=None, help="optional run id")
    replay_parser.add_argument("--event-type", default=None, help="optional event type filter")
    replay_parser.add_argument("--format", choices=("json", "text"), default="json", help="output format")

    report_parser = subparsers.add_parser("report", help="summarize one or more event-log runs")
    report_parser.add_argument("--event-log", type=Path, required=True, help="sqlite event log path")
    report_parser.add_argument("--run-id", default=None, help="optional run id")
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
    event_log = SQLiteEventLog(config.event_log)
    try:
        runner = AgentRunner(
            provider=build_llm_adapter(config.provider),
            event_log=event_log,
            tools=build_default_tools(root=Path.cwd()),
            safety_policy=config.safety,
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
    finally:
        event_log.close()


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
        target = event.payload.get("tool", event.payload.get("metadata", {}))
        detail = f" kind={event.payload.get('kind')} target={target}"
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


if __name__ == "__main__":
    raise SystemExit(main())
