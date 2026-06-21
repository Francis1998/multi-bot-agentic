# multi-bot-agentic

`multi-bot-agentic` is a standalone portfolio-grade AI-agent orchestrator. It demonstrates a deterministic **Observe -> Decide -> Act** loop, durable event logs, multi-provider LLM adapters, explicit lifecycle transitions, safety controls, and replayable rationale traces.

The repo is intentionally local-first: it runs with a deterministic fake provider in CI and demos, while also including adapters for GPT/OpenAI, Claude Code CLI, Gemini, and Kimi/Moonshot.

## Quick Demo

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy src tests
pytest
multi-bot-agentic run --goal "Create a launch checklist for an AI agent platform" --provider fake
```

## What This Showcases

- Explicit Observe -> Decide -> Act runtime loop.
- Deterministic decision engine with rationale traces.
- State-machine lifecycle: created, observing, deciding, acting, succeeded, failed, cancelled.
- Durable sqlite event log with replay.
- LLM adapters for OpenAI GPT, Claude Code CLI, Gemini, and Kimi/Moonshot.
- Tool adapters with allowlisted execution.
- Safety controls for max steps, prompt bounds, cancellation, and timeouts.
- Production-minded layout: `src/`, `tests/`, `scripts/`, `migrations/`, `.github/workflows/`, env config, docs.

## Documentation

- [Quickstart](docs/QUICKSTART.md)
- [Configuration](docs/CONFIGURATION.md)
- [Safety](docs/SAFETY.md)
- [Architecture](docs/ARCHITECTURE.md)

## Demo

See `docs/demo.svg` for a visual walkthrough and run `scripts/run_demo.sh` for a local CLI replay.
