# Quickstart

## Install

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Verify

```bash
ruff check .
ruff format --check .
mypy src tests
pytest
```

## Run A Deterministic Demo

```bash
multi-bot-agentic run \
  --goal "Create a launch checklist for an AI agent platform" \
  --provider fake \
  --event-log data/runs.sqlite
```

## Replay The Durable Event Log

```bash
multi-bot-agentic replay --event-log data/runs.sqlite
```

## Run The Scripted Demo

```bash
scripts/run_demo.sh
```

The demo uses the fake provider and writes a replayable sqlite event log under `demo-output/`.

## Try A Live Provider

```bash
export OPENAI_API_KEY=...
multi-bot-agentic run \
  --goal "Return DONE: with a short release checklist" \
  --provider openai \
  --max-steps 4
```

Live providers are not required for tests or CI.
