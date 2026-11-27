#!/usr/bin/env bash
set -euo pipefail

ruff check .
ruff format --check .
mypy src tests
pytest
rm -f /tmp/multi-bot-agentic-check.sqlite
PYTHONPATH=src python -m multi_bot_agentic.cli run \
  --goal "Create a launch checklist for an AI agent platform" \
  --provider fake \
  --max-steps 5 \
  --run-id check-smoke \
  --event-log /tmp/multi-bot-agentic-check.sqlite
PYTHONPATH=src python -m multi_bot_agentic.cli replay \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --event-type decision \
  --format text
PYTHONPATH=src python -m multi_bot_agentic.cli report \
  --event-log /tmp/multi-bot-agentic-check.sqlite
PYTHONPATH=src python -m multi_bot_agentic.cli trace \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --format otlp-json
PYTHONPATH=src python -m multi_bot_agentic.cli trace \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --format mermaid
PYTHONPATH=src python -m multi_bot_agentic.cli history \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --run-id check-smoke
PYTHONPATH=src python -m multi_bot_agentic.cli fork \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --run-id check-smoke \
  --at-step 1 \
  --new-run-id check-smoke-fork \
  --goal "Create a rollback checklist for an AI agent platform" \
  --provider fake \
  --max-steps 6
PYTHONPATH=src python -m multi_bot_agentic.cli report \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --run-id check-smoke-fork
PYTHONPATH=src python -m multi_bot_agentic.cli trace \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --run-id check-smoke-fork \
  --format mermaid
# Human-in-the-loop interrupt: the run pauses before the gated tool (exit 3), a human approves, resume finishes it.
status=0
PYTHONPATH=src python -m multi_bot_agentic.cli run \
  --goal "Create a launch checklist for an AI agent platform" \
  --provider fake \
  --run-id check-hitl \
  --require-approval checklist \
  --event-log /tmp/multi-bot-agentic-check.sqlite || status=$?
test "$status" -eq 3
PYTHONPATH=src python -m multi_bot_agentic.cli approvals list \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --run-id check-hitl
PYTHONPATH=src python -m multi_bot_agentic.cli approve \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --run-id check-hitl \
  --by check-script \
  --reason "smoke test"
PYTHONPATH=src python -m multi_bot_agentic.cli resume \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --run-id check-hitl
PYTHONPATH=src python -m multi_bot_agentic.cli replay \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --run-id check-hitl \
  --event-type approval_decision \
  --format text
# Structured output: the fake provider's first answer is plain text, so one correction round runs
# before the JSON validates and is written to the output file; with no correction rounds the run exits 4.
rm -f /tmp/multi-bot-agentic-check.sqlite.output.json
PYTHONPATH=src python -m multi_bot_agentic.cli run \
  --goal "Plan the agent launch" \
  --provider fake \
  --run-id check-output \
  --output-schema examples/structured-output/launch-plan.schema.json \
  --output-file /tmp/multi-bot-agentic-check.sqlite.output.json \
  --event-log /tmp/multi-bot-agentic-check.sqlite
python -m json.tool /tmp/multi-bot-agentic-check.sqlite.output.json
PYTHONPATH=src python -m multi_bot_agentic.cli replay \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --run-id check-output \
  --event-type output_validation_failed \
  --format text
status=0
PYTHONPATH=src python -m multi_bot_agentic.cli run \
  --goal "Plan the agent launch" \
  --provider fake \
  --run-id check-output-invalid \
  --output-schema examples/structured-output/launch-plan.schema.json \
  --output-retries 0 \
  --event-log /tmp/multi-bot-agentic-check.sqlite || status=$?
test "$status" -eq 4
