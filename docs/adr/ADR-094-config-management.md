# ADR-094: Config Management for multi-bot-agentic

**Date:** 2024-06-19
**Status:** Accepted
**Context:** Multi-Agent Orchestration

## Context

The `multi_bot_agentic` module needs a reliable config management solution
that integrates cleanly with our async safety pipeline.

## Decision

Use **pydantic-settings** for config management.

## Considered Alternatives

| Option | Pros | Cons |
|--------|------|------|
| **pydantic-settings** (chosen) | Native async, well-maintained | Slightly higher cold-start |
| dynaconf | Mature ecosystem | Sync-first, harder to integrate |
| raw os.environ | Zero dependencies | Limited features for production |

## Consequences

- All new safety components will use `pydantic-settings` as the config management layer.
- Existing code will be migrated incrementally.
- Added to `pyproject.toml` as a core dependency.
