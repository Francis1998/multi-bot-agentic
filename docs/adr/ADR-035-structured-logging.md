# ADR-035: Structured Logging for multi-bot-agentic

**Date:** 2024-11-07
**Status:** Accepted
**Context:** Multi-Agent Orchestration

## Context

The `multi_bot_agentic` module needs a reliable structured logging solution
that integrates cleanly with our async event pipeline.

## Decision

Use **structlog** for structured logging.

## Considered Alternatives

| Option | Pros | Cons |
|--------|------|------|
| **structlog** (chosen) | Native async, well-maintained | Slightly higher cold-start |
| loguru | Mature ecosystem | Sync-first, harder to integrate |
| stdlib logging | Zero dependencies | Limited features for production |

## Consequences

- All new event components will use `structlog` as the structured logging layer.
- Existing code will be migrated incrementally.
- Added to `pyproject.toml` as a core dependency.
