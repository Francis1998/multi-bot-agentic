"""Command-line interface for multi-bot-agentic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from multi_bot_agentic.config import AppConfig, build_llm_adapter
from multi_bot_agentic.event_log import SQLiteEventLog
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
            print(
                json.dumps(
                    {
                        "run_id": event.run_id,
                        "seq": event.seq,
                        "timestamp": event.timestamp,
                        "event_type": event.event_type,
                        "state": event.state,
                        "payload": event.payload,
                    },
                    sort_keys=True,
                )
            )
    finally:
        event_log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
