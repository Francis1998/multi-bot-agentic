# Safety

`multi-bot-agentic` treats the LLM as an input source, not an authority. Model outputs are consumed as observations, then a deterministic decision engine chooses the next action.

## Controls

- **Bounded scope**: prompts are capped by `max_prompt_chars`.
- **Bounded runtime**: runs stop at `max_steps`.
- **Timeouts**: each provider call has a timeout.
- **Cancellation**: a cancellation file can stop a run before the next action.
- **Tool allowlist**: tools must be registered and allowed by policy.
- **Rationale traces**: every decision records matched rule IDs, inputs used, and rejected actions.

## What The LLM Can And Cannot Do

The LLM can return text. The decision engine interprets two prefixes:

- `TOOL:<tool_name>:<payload>` requests an allowlisted tool.
- `DONE:<answer>` requests completion.

Anything else becomes another observation and is handled deterministically. The LLM cannot directly call Python functions, shell commands, or filesystem APIs.

## Tool Boundary

Tools implement `ToolAdapter`. The default registry includes:

- `checklist`: deterministic launch checklist generator.
- `echo`: safe deterministic echo tool for demos.
- `readonly_file`: root-contained read-only file access.

Unknown tools are rejected by `SafetyPolicy.validate_tool()`.

## Cancellation

Set `MULTIBOT_CANCEL_FILE=/path/to/cancel`. If that file exists before the next action, the run transitions to `cancelled` and persists a `run_cancelled` event.

## Provider Credentials

Credentials are read from environment variables and are never written to the event log. Event payloads store normalized provider output text and metadata, not secret values.

## Known Limits

This repo does not expose a network service or remote terminal control. If adapted into a server, add authentication, authorization, request auditing, workspace isolation, and per-user quota enforcement before exposing it beyond localhost.
