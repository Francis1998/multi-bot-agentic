# Use Cases

Real problems **multi-bot-agentic** solves — starting from issues.

| Issue | Title | Doc |
|-------|-------|-----|
| #001 | Non-deterministic agent loops hard to debug | [ISSUE-001](./ISSUE-001-non-deterministic-agent-loops-hard-to-de.md) |
| #002 | Long-running tasks need cancellation | [ISSUE-002](./ISSUE-002-long-running-tasks-need-cancellation.md) |
| #003 | Tool failures should not crash the run | [ISSUE-003](./ISSUE-003-tool-failures-should-not-crash-the-run.md) |
| #004 | Invalid step budgets should fail fast | [ISSUE-004](./ISSUE-004-invalid-step-budgets-should-fail-fast.md) |

## Design pillars

- Deterministic decision engine with rationale traces
- State-machine run lifecycle + durable event log
- Tool/adapter abstraction (GPT, Claude, Gemini, Kimi)
- Safety: timeouts, bounded scope, cancellation
