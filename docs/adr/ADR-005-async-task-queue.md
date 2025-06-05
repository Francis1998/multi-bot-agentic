# ADR-005: Async Task Queue for multi-bot-agentic

**Date:** 2025-06-04
**Status:** Accepted
**Context:** Multi-Agent Orchestration

## Context

The `multi_bot_agentic` module needs a reliable async task queue solution
that integrates cleanly with our async bot pipeline.

## Decision

Use **Redis Streams** for async task queue.

## Considered Alternatives

| Option | Pros | Cons |
|--------|------|------|
| **Redis Streams** (chosen) | Native async, well-maintained | Slightly higher cold-start |
| Celery + RabbitMQ | Mature ecosystem | Sync-first, harder to integrate |
| asyncio.Queue | Zero dependencies | Limited features for production |

## Consequences

- All new bot components will use `Redis Streams` as the async task queue layer.
- Existing code will be migrated incrementally.
- Added to `pyproject.toml` as a core dependency.
