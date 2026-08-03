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
- `content_type_sniff`: sniffs likely content type from a bounded text or base64 byte prefix (`json`, `xml`, `html`, `csv`, `tsv`, `markdown`, `plain`) and returns confidence; rejects empty/oversized input; never executes code or makes network requests.
- `echo`: safe deterministic echo tool for demos.
- `readonly_file`: root-contained read-only file access.
- `calculator`: sandboxed AST arithmetic; refuses non-real and non-finite results, bounds the exponent, and rejects results whose integer magnitude exceeds a fixed bit bound (stops nested power towers).
- `json_format`: JSON validation and canonicalization.
- `yaml_format`: validates and canonicalizes a constrained YAML subset (block mappings/sequences, JSON-style flow collections, scalar values); rejects anchors, aliases, tags, document markers, constructors, malformed indentation, oversized input, and non-finite numbers; never executes code.
- `zip_list`: lists ZIP archive member metadata (`name`, `size`, `compress_size`, `date`) from base64-encoded bytes via stdlib `zipfile`; rejects empty/oversized input, invalid base64, and non-ZIP payloads; never extracts or executes archive members.
- `toml_format`: validates TOML via `tomllib` (Python 3.11+) or `tomli` when available and returns a deterministic serialization (sorted keys; tables/arrays/strings/ints/floats/bools); rejects empty/oversized input, dates/times, non-finite floats, and missing parsers; never executes code.
- `toml_json`: converts between TOML and JSON text (`direction`: `to_json` default or `to_toml`); uses the same portable dict/list/str/int/float/bool subset as `toml_format`/`json_format`; rejects empty/oversized input, dates/times, JSON null, non-finite numbers, and missing parsers; never executes code.
- `tsv_format`: validates tab-separated values via stdlib `csv` (`excel-tab` dialect) and returns canonical TSV with consistent newlines; rejects empty/oversized input, uneven column counts (header defines width), and trailing blank rows are stripped; never executes code.
- `csv_groupby`: groups CSV rows by key columns and aggregates numeric value columns via stdlib `csv` (`agg`: `sum` default, `count`, `min`, `max`, `mean`); rejects empty/oversized/malformed input, unknown columns, and non-numeric values; never executes code or makes network requests.
- `csv_pivot`: pivots long CSV to wide or unpivots via stdlib `csv` (`mode`: `pivot` default or `unpivot`); rejects empty/oversized/malformed input and unknown columns; never executes code or makes network requests.
- `csv_tsv`: converts between CSV and TSV text (`direction`: `csv_to_tsv` default or `tsv_to_csv`); optional single-character input `delimiter` override; rejects empty/oversized input, invalid direction/delimiter, uneven column counts, and malformed tables; never executes code.
- `xml_parse`: parses XML via stdlib `xml.etree.ElementTree` into a compact indented text tree (tags, `@attr=value`, text nodes); rejects empty/oversized input, DOCTYPE/ENTITY declarations (XXE hardening), and malformed XML; depth- and element-capped rendering; never executes code.
- `json_path`: extracts values from JSON via a simple dot/[index] path (`text`+`path`, or `text` split on `<<<JSON_PATH>>>`); rejects recursive descent, filters, scripts, pipes, oversized input/results, and invalid JSON; never executes code.
- `json_query`: filters JSON object arrays (`where` field==value) or plucks a field (`pluck`) via stdlib `json`; rejects empty/oversized/malformed input and unsupported mode; never executes code, evaluates scripts, or makes network requests.
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
- `text_sort_lines`: sorts text lines ascending or descending (`order`: `asc`/`desc`, default `asc`); optional `unique` dedupe after sort; rejects empty/oversized input and unsupported order; never executes code.
- `unicode_normalize`: normalizes Unicode text via stdlib `unicodedata` (`form`: NFC default, NFD, NFKC, NFKD); rejects empty/oversized input and unsupported forms; never executes code or makes network requests.
- `text_wrap`: wraps or fills text via stdlib `textwrap` (`mode`: `wrap` default or `fill`, `width` default 80, range 1..500); rejects empty/oversized input, invalid width, and unsupported mode; never executes code or makes network requests.
- `csv`: parses CSV text into canonical JSON (header + rows); caps rows/columns; optional single-character `delimiter`; never executes code.
- `html_entities`: encodes or decodes HTML entities via stdlib `html` (`mode`: `encode` default or `decode`; encode optionally escapes quotes); rejects empty/oversized input, unsupported mode, and invalid quote; never executes code or makes network requests.
- `html_strip`: strips HTML tags to plain text via stdlib `html.parser`; rejects documents containing `script`/`style`; empty or oversized input returns `ok=False`; never executes code.
- `html_markdown`: converts safe HTML fragments to Markdown (headings, links, lists, bold/italic, code, paragraphs) via stdlib `html.parser`; rejects documents containing `script`/`style`; empty or oversized input returns `ok=False`; never executes code or makes network requests.
- `html_table_csv`: converts the first HTML table (default) or all tables (`all=true`) to CSV text via stdlib `html.parser`; rejects documents containing `script`/`style`; empty, oversized, or table-less input returns `ok=False`; never executes code or makes network requests.
- `markdown_table`: renders CSV-like text or list-of-rows input as a GitHub-flavored markdown table; caps rows/columns; escapes pipe/newline cell content; never executes code.
- `mime_multipart`: parses a raw MIME message via stdlib `email` and returns JSON summaries of each part (`content_type`, `charset`, `size`, `payload_preview`); rejects empty/oversized input; never executes code, extracts attachments to disk, or makes network requests.
- `template_render`: renders `{var}` / `{{ var }}` placeholders from scalar JSON variables (`template`+`variables`, or `text` split on `<<<TEMPLATE_VARS>>>`); HTML-escapes substitutions; rejects expressions, filters, attribute lookup, unsupported brace syntax, nested variables, and oversized output; never executes code.

Unknown tools are rejected by `SafetyPolicy.validate_tool()`.

## Cancellation

Set `MULTIBOT_CANCEL_FILE=/path/to/cancel`. If that file exists before the next action, the run transitions to `cancelled` and persists a `run_cancelled` event.

## Provider Credentials

Credentials are read from environment variables and are never written to the event log. Event payloads store normalized provider output text and metadata, not secret values.

## Known Limits

This repo does not expose a network service or remote terminal control. If adapted into a server, add authentication, authorization, request auditing, workspace isolation, and per-user quota enforcement before exposing it beyond localhost.
