# ADR-093: Database Orm for multi-bot-agentic

**Date:** 2025-06-16
**Status:** Accepted
**Context:** Multi-Agent Orchestration

## Context

The `multi_bot_agentic` module needs a reliable database ORM solution
that integrates cleanly with our async rationale pipeline.

## Decision

Use **SQLAlchemy 2.0** for database ORM.

## Considered Alternatives

| Option | Pros | Cons |
|--------|------|------|
| **SQLAlchemy 2.0** (chosen) | Native async, well-maintained | Slightly higher cold-start |
| Tortoise ORM | Mature ecosystem | Sync-first, harder to integrate |
| raw SQL | Zero dependencies | Limited features for production |

## Consequences

- All new rationale components will use `SQLAlchemy 2.0` as the database ORM layer.
- Existing code will be migrated incrementally.
- Added to `pyproject.toml` as a core dependency.
