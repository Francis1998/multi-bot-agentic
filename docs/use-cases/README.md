# Use Cases

Real problems **multi-bot-agentic** solves.

- **End-to-end walkthrough:** [An auditable release-readiness bot that uses MCP tools](USE-CASE-mcp-release-readiness.md).
  Every command was actually run.
- **Problems this solves:** [eleven everyday agent-engineering problems](PROBLEMS_THIS_SOLVES.md) and how the
  design addresses each.
- **Observe runs in your tracing backend:** export any recorded run as an OpenTelemetry GenAI trace for Jaeger,
  Grafana Tempo, or Langfuse, or as a Mermaid sequence diagram of the bots, tools, and handoffs. See the
  [OpenTelemetry Trace Export Guide](../guides/OTEL_TRACE_EXPORT_GUIDE.md) and
  [problem 11](PROBLEMS_THIS_SOLVES.md#11-i-want-to-see-agent-runs-in-our-tracing-backend-not-a-terminal).
- **Issue stories:** regression write-ups from real fixes, listed below.

| Issue | Title | Doc |
|-------|-------|-----|
| #001 | Non-deterministic agent loops hard to debug | [ISSUE-001](./ISSUE-001-non-deterministic-agent-loops-hard-to-de.md) |
| #002 | Long-running tasks need cancellation | [ISSUE-002](./ISSUE-002-long-running-tasks-need-cancellation.md) |
| #003 | Tool failures should not crash the run | [ISSUE-003](./ISSUE-003-tool-failures-should-not-crash-the-run.md) |
| #004 | Invalid step budgets should fail fast | [ISSUE-004](./ISSUE-004-invalid-step-budgets-should-fail-fast.md) |
| #005 | Unreadable files should not crash the run | [ISSUE-005](./ISSUE-005-unreadable-files-should-not-crash-the-run.md) |
| #006 | A provider timeout should fail the run, not crash the process | [ISSUE-006](./ISSUE-006-provider-timeout-should-not-crash-the-run.md) |
| #007 | OpenAI-compatible gateways may return structured content | [ISSUE-007](./ISSUE-007-openai-compatible-structured-content.md) |
| #008 | The calculator tool must return real numbers only | [ISSUE-008](./ISSUE-008-calculator-complex-results.md) |
| #009 | The calculator tool must return finite numbers only | [ISSUE-009](./ISSUE-009-calculator-non-finite-results.md) |
| #010 | Replay timelines must not leak provider metadata | [ISSUE-010](./ISSUE-010-replay-timeline-leaks-metadata.md) |
| #011 | PII redaction missed parenthesized area-code phone numbers | [ISSUE-011](./ISSUE-011-redaction-misses-parenthesized-phone.md) |
| #012 | PII redaction over-redacted invalid IPv4-looking numbers | [ISSUE-012](./ISSUE-012-redaction-over-redacts-invalid-ipv4.md) |
| #013 | The calculator tool must bound nested power towers | [ISSUE-013](./ISSUE-013-calculator-nested-power-tower.md) |
| #014 | Slugify must not eat edge letters with alphanumeric separators | [ISSUE-014](./ISSUE-014-slugify-alphanumeric-separator-strip.md) |

## Design pillars

- Deterministic decision engine with rationale traces
- State-machine run lifecycle + durable event log
- Tool/adapter abstraction (GPT-6, Claude 5.5 and Fable 5.2 via Claude Code, Gemini 3.8 Flash / 4 Hydrogen / 4 Carbon / 4 Argon, Kimi K3.1, and any MCP server)
- Safety: timeouts, bounded scope, cancellation
- Built-in compare tool (`diff`) for trustworthy before/after observations
