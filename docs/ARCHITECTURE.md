# Architecture

The runtime is a deterministic control plane around LLM and tool adapters. The LLM can propose text such as `TOOL:echo:<payload>` or `DONE:<answer>`, but it never directly executes tools.

## Runtime Loop

The core loop lives in `AgentRunner.run()`:

```text
Observe -> Decide -> Act -> Observe -> ...
```

## Observe

The runner gathers observations from the initial goal, provider outputs, and tool results. Observations are durable events.

Observation examples:

- user goal
- normalized provider output
- tool result
- cancellation signal

## Decide

The deterministic decision engine evaluates observations and safety policy. It emits a `Decision` with a `RationaleTrace` that records why an action was chosen and which alternatives were rejected.

Current deterministic rules:

- `safety.cancel-file`: cancel if the configured cancellation file exists.
- `observe.no-model-output`: call the selected provider first.
- `model.requested-tool`: call an allowlisted tool for `TOOL:<name>:<payload>`.
- `tool.result-needs-synthesis`: send tool results back to the provider.
- `model.done-or-budget`: finish on `DONE:<answer>` or final budget step.
- `model.needs-followup`: call the provider again for non-final text.

## Act

Actions are limited to provider calls, allowlisted tools, finish, fail, or cancel. The LLM never directly invokes tools.

## Durable Event Log

The sqlite event log stores every lifecycle transition, observation, decision, action request, action result, and failure with a per-run sequence number. A run can be replayed without calling a provider.

## Provider Adapters

All providers implement one interface:

```text
ModelRequest -> ModelOutput
```

Adapters normalize GPT/OpenAI, Claude Code CLI, Gemini, Kimi/Moonshot, and the deterministic fake provider.

## State Machine

```text
created
  -> observing
  -> deciding
  -> acting
  -> observing
  -> deciding
  -> succeeded | failed | cancelled
```

Invalid transitions raise `InvalidTransitionError` and are covered by tests.

## Replay

Replay reads sqlite events and prints them in sequence. Replay never calls providers or tools, so it is safe to run in CI and postmortems.
