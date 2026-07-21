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
- `calculator`: sandboxed AST arithmetic; refuses non-real and non-finite results, bounds the exponent, and rejects results whose integer magnitude exceeds a fixed bit bound (stops nested power towers).
- `json_format`: JSON validation and canonicalization.
- `redact`: scrubs PII (email, phone, SSN, IPv4, IPv6) from text into typed placeholders.
- `hash`: computes a hex digest of text (md5, sha1, sha256, sha512; default sha256).
- `base64`: encodes text to Base64 or decodes Base64 to text (encode|decode; default encode).
- `url_parse`: splits an absolute URL into scheme, host, port, path, query, and fragment.
- `uuid5`: computes a deterministic version-5 UUID from a name and namespace (dns|url|oid|x500|custom UUID; default dns).
- `slugify`: converts text into a URL-safe ASCII slug (separator default `-`, optional `max_length` truncated on a word boundary).
- `datetime`: normalizes an ISO-8601 timestamp to canonical UTC (with epoch and weekday); reads no wall-clock `now` and requires `assume_utc` for naive input.
- `duration`: parses an ISO-8601 duration into total seconds and a component breakdown; supports only fixed-length components (weeks/days/hours/minutes/seconds) and refuses calendar years/months; designators are case-insensitive (`pt1h30m` == `PT1H30M`); reads no wall-clock `now`.
- `diff`: produces a unified diff between two texts (`text`+`other`, or `text` split on `<<<DIFF>>>` with or without surrounding newlines); bounds each side and the output line count; never executes code.
- `regex`: extracts regex matches from text (`text`+`pattern`, or `text` split on `<<<REGEX>>>`); returns canonical JSON of spans/groups; bounds document/pattern size and match count; never executes code.
- `truncate`: truncates text to a max length (`max_length` arg, or `text` split on `<<<TRUNCATE>>>`, default 256); optional custom `ellipsis`; bounds input size; never executes code.
- `csv`: parses CSV text into canonical JSON (header + rows); caps rows/columns; optional single-character `delimiter`; never executes code.

Unknown tools are rejected by `SafetyPolicy.validate_tool()`.

## Cancellation

Set `MULTIBOT_CANCEL_FILE=/path/to/cancel`. If that file exists before the next action, the run transitions to `cancelled` and persists a `run_cancelled` event.

## Provider Credentials

Credentials are read from environment variables and are never written to the event log. Event payloads store normalized provider output text and metadata, not secret values.

## Known Limits

This repo does not expose a network service or remote terminal control. If adapted into a server, add authentication, authorization, request auditing, workspace isolation, and per-user quota enforcement before exposing it beyond localhost.
