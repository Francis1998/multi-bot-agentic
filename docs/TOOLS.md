# Built-In Tools

Every built-in tool implements `ToolAdapter`, is registered in `build_default_tools()`, and is allowlisted
by `SafetyPolicy`. A model requests one with `TOOL:<name>:<payload>`. Tools run offline and in-process, reject
oversized input, and never make network requests. Most are deterministic; generators such as `uuid4` and `ulid`
are not. For tools from external servers, see the [MCP Tool Bridge Guide](guides/MCP_TOOLS_GUIDE.md).

> Entries below were moved **verbatim** from the former README. Model names in them (GPT-5.5, Claude
> Sonnet 4.6, Gemini 3.x, Kimi K2) are historical. See
> [Current Model Stack](CONFIGURATION.md#current-model-stack).

## Tools

- `checklist`: deterministic launch checklist generator used by the fake-provider demo.
- `content_type_sniff`: sniffs likely content type from a bounded text or base64
  byte prefix (`json`, `xml`, `html`, `csv`, `tsv`, `markdown`, `plain`) and
  returns a confidence score without network access. Empty or oversized input
  returns a structured failure. A model requests it with
  `TOOL:content_type_sniff:<payload>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini
  3.x / Kimi K2 workers that need a parser hint before the next step.
- `cron_next`: returns the next N UTC fire times for a classic 5-field cron expression (`count` default 5, max 20; optional `from_iso`). Invalid fields return a structured failure. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 scheduling agents.
- `echo`: safe text echo for adapter tests.
- `readonly_file`: root-contained read-only file reader.
- `calculator`: sandboxed arithmetic evaluator. It parses expressions into an AST
  and walks an allowlist of numeric literals and `+ - * / // % **` operators —
  never `eval` — so names, calls, and attribute access are rejected and exponents
  are bounded against CPU/memory exhaustion. Results that are not real numbers
  (for example a fractional power of a negative base) or not finite (overflow to
  `inf`, or `nan`) are refused rather than returned as opaque values. A model
  requests it with `TOOL:calculator:2 + 3 * 4`, matching the same
  model-suggests / policy-validates / adapter-executes pattern as every other
  tool.
- `json_format`: validates a JSON document and returns it canonicalized (sorted
  keys, 2-space indent). Invalid input yields a structured failure with the
  parser's message instead of raising, and the non-standard `NaN`/`Infinity`/
  `-Infinity` tokens (which RFC 8259 forbids and strict parsers reject) are
  rejected rather than round-tripped into invalid output. A model requests it
  with `TOOL:json_format:{"b":1,"a":2}`, giving agents a safe way to verify and
  normalize JSON produced by earlier steps.
- `uuid_nil`: returns the RFC 4122 nil UUID `00000000-0000-0000-0000-000000000000` (default) or the max UUID when `mode=max`. Useful as a placeholder id in crewAI / LangGraph-style agent pipelines. Unsupported modes return a structured failure. A model requests it with `TOOL:uuid_nil:` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need a stable sentinel identifier.
- `yaml_format`: validates a constrained safe YAML subset and returns it
  canonicalized (sorted mapping keys, 2-space indentation). It supports block
  mappings/sequences, JSON-style flow collections, and finite scalar values
  using the Python stdlib only; unsupported full-YAML features such as anchors,
  tags, document markers, and constructors return structured failures. A model
  requests it with `TOOL:yaml_format:enabled: true`, giving agents a safe way to
  normalize YAML handoff snippets.
- `toml_format`: validates TOML (via `tomllib` on Python 3.11+ or `tomli` when
  available) and returns a deterministic serialization with sorted keys for
  tables/arrays/strings/ints/floats/bools. Dates/times, non-finite floats, empty
  or oversized input, and a missing parser return structured failures. A model
  requests it with `TOOL:toml_format:enabled = true`, giving agents a safe way to
  normalize TOML configuration snippets.
- `toml_json`: converts between TOML and JSON text for agent handoffs
  (`direction`: `to_json` default or `to_toml`). Parsing uses `tomllib`/`tomli`
  or strict `json.loads`; output is canonical JSON (sorted keys, 2-space indent)
  or deterministic TOML (same dumper as `toml_format`). Dates/times, JSON null,
  non-finite numbers, empty or oversized input, and missing parsers return
  structured failures. A model requests it with `TOOL:toml_json:enabled = true`,
  giving agents a safe way to bridge TOML configuration and JSON payloads.
- `tsv_format`: validates tab-separated spreadsheet text via stdlib `csv`
  (`excel-tab` dialect) and returns canonical TSV with consistent newlines.
  Empty or oversized input, uneven column counts (header defines width), and
  malformed tables return structured failures; trailing blank rows are stripped.
  A model requests it with `TOOL:tsv_format:model\tscore`, giving agents a safe
  way to normalize TSV handoff snippets.
- `json_merge_patch`: applies RFC 7396 JSON Merge Patch (`base`+`patch`,
  or `text` with `<<<PATCH>>>`) via stdlib `json`. Empty, oversized,
  malformed, or over-deep requests return a structured failure. A model
  requests it with `TOOL:json_merge_patch:<json>` for GPT-5.5 /
  Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need deterministic
  partial JSON updates.
- `line_number`: prefixes each text line with a 1-based line number
  (optional `start` / `separator`). Empty or oversized input and invalid
  start/separator values return a structured failure. A model requests it
  with `TOOL:line_number:<text>` for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 workers that need stable line citations.
- `csv_filter`: filters CSV rows where a named column equals or contains a
  value (`mode`: `equals` default or `contains`; `case_insensitive`: true
  default) via stdlib `csv`. Empty, oversized, malformed, unknown-column, or
  over-bounds requests return a structured failure. A model requests it with
  `TOOL:csv_filter:<csv><<<CSV_FILTER>>>column<<<=>>>value` (or
  `column<<<~>>>value`) for deterministic tabular predicates before the next
  turn.
- `csv_groupby`: groups CSV rows by key columns and aggregates numeric
  value columns (`agg`: `sum` default, `count`, `min`, `max`, `mean`) via
  stdlib `csv`. Empty, oversized, malformed, unknown-column, or non-numeric
  requests return a structured failure. A model requests it with
  `TOOL:csv_groupby:<csv>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 workers that need deterministic tabular aggregation before the
  next turn.
- `csv_join`: joins two CSV tables on a key column (`how`: `inner` default or
  `left`; `on` or `left_on`+`right_on`) via stdlib `csv`. Supply sides as
  `left`+`right`, or `text`+`right`. Empty, oversized, malformed, or
  unknown-column requests return a structured failure. A model requests it
  with `TOOL:csv_join:<csv>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 workers that need deterministic tabular lookup joins before the
  next turn.
- `csv_pivot`: pivots long CSV to wide (`index`/`columns`/`values`) or
  unpivots wide columns (`id_vars`/`value_vars`) via stdlib `csv`. Empty,
  oversized, malformed, or unknown-column requests return a structured
  failure. A model requests it with `TOOL:csv_pivot:<csv>` for GPT-5.5 /
  Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need deterministic
  tabular reshape before the next turn.
- `csv_stack`: vertically concatenates CSV documents that share an identical
  header, accepting a `csvs` list or `text` split by `<<<CSV_STACK>>>`. It
  rejects malformed input, mismatched headers, uneven rows, and bounded-size
  violations for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
- `csv_tsv`: converts between CSV and TSV text for agent handoffs
  (`direction`: `csv_to_tsv` default or `tsv_to_csv`). Parsing and serialization
  use stdlib `csv` only; an optional single-character `delimiter` overrides the
  input separator. Empty or oversized input, invalid direction/delimiter,
  uneven column counts, and malformed tables return structured failures. A model
  requests it with `TOOL:csv_tsv:model,score`, giving agents a safe way to bridge
  CSV and TSV handoff snippets across GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 workers.
- `xml_escape`: escapes or unescapes XML special characters (`&`, `<`, `>`) via stdlib `xml.sax.saxutils.escape`/`unescape` (`mode: escape|unescape`; default `escape`). Empty, oversized, or unsupported-mode requests return a structured failure. A model requests it with `TOOL:xml_escape:<text>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need deterministic XML entity escaping.
- `xml_parse`: parses XML via stdlib `xml.etree.ElementTree` into a compact
  indented text tree (tag names, `@attr=value` pairs, direct text nodes).
  Empty or oversized input, DOCTYPE/ENTITY declarations (XXE hardening), and
  malformed XML return structured failures; rendering is depth- and
  element-capped. A model requests it with `TOOL:xml_parse:<root>...</root>`,
  giving agents a safe way to summarize XML handoff snippets.
- `json_path`:
- `json_pointer`: extracts one value from a JSON document using RFC 6901 JSON Pointer (`/foo/0/bar`, `~0`/`~1` escapes); agents may split document and pointer on `<<<JSON_POINTER>>>` for `TOOL:json_pointer:...` directives. Distinct from `json_path`.
PLACEHOLDER
- `jwt_decode`: base64url-decodes a JWT header and payload into JSON claims without verifying the signature. Empty, oversized, or malformed tokens return a structured failure. Output is never trusted as authenticated. A model requests it with `TOOL:jwt_decode:<jwt>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need opaque claim inspection.
- `json_query`: filters JSON object arrays (`where` field equals
  value) or plucks a field across objects (`pluck`) via stdlib
  `json`. Empty, oversized, malformed, or unsupported-mode requests
  return a structured failure. A model requests it with
  `TOOL:json_query:<json><<<JSON_QUERY>>>{...}` for GPT-5.5 /
  Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need
  deterministic array select beyond `json_path`.
- `json_path_KEEP`: extracts one value from a JSON document using a small deterministic
  path dialect (`.foo.bar`, `items[0].name`, or `$`/empty for the whole document).
  Supply `text`+`path`, or a single payload split on `<<<JSON_PATH>>>` for
  `TOOL:json_path:...` directives. Recursive descent, filters, scripts, pipes,
  oversized input, and oversized serialized results return structured failures;
  the tool uses `json.loads` only and never executes code.
- `spreadsheet_slice`: parses CSV text and returns a deterministic row/column
  subset as JSON (`header` + `rows`). Row ranges use zero-based, end-exclusive
  body-row slices via `rows=1:3` or `row_start`/`row_end`; columns may be selected
  by exact header name and/or zero-based index. A single `TOOL:spreadsheet_slice`
  payload can embed options after `<<<SPREADSHEET_SLICE>>>`. Empty input,
  oversized tables, blank headers, invalid ranges, missing names, ambiguous
  names, and out-of-bounds indexes return structured failures; the tool uses
  stdlib `csv` only and never executes code.
- `redact`: scrubs common PII (email addresses, phone numbers, US Social
  Security numbers, IPv4 addresses) from text, replacing each match with a typed
  placeholder such as `[EMAIL]` and reporting per-category counts in the tool
  metadata. A model requests it with `TOOL:redact:<text>`, giving agents a safe
  way to sanitize content before it is persisted to the durable event log.
- `hash`: computes a hex digest of text with a small allowlist of well-known
  algorithms (`md5`, `sha1`, `sha256`, `sha512`; default `sha256`). Empty,
  oversized, or unsupported-algorithm requests return a structured failure. A
  model requests it with `TOOL:hash:<text>`, giving agents a deterministic
  fingerprint for deduplication, cache keys, or integrity checks between steps.
- `base58`: encodes text to Bitcoin-alphabet Base58 or decodes Base58 back to text (`mode: encode|decode`; default `encode`; accepts `text` or `data`). Decoding requires valid Base58 that yields UTF-8; empty, oversized, unsupported-mode, or invalid payloads return a structured failure. A model requests it with `TOOL:base58:<text>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need lookalike-safe opaque handoffs.
- `pluralize`: pluralize/singularize a single English word (`mode: pluralize|singularize`; accepts `text` or `word`; common irregulars; max 2000 chars). Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
- `punycode`: encode/decode domain text via Punycode/IDNA (`mode: encode|decode`; accepts `text` or `domain`; max 2000 chars). Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
- `base85`: encodes text to Adobe ASCII85/Base85 or decodes back (`mode: encode|decode`; default `encode`; accepts `text` or `data`). Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
- `base32_encode`: encodes text to standard Base32 or decodes Base32 back to text (`mode: encode|decode`; default `encode`) via stdlib `base64.b32encode`/`b32decode`. Decoding requires valid Base32 that yields UTF-8; empty, oversized, unsupported-mode, or invalid payloads return a structured failure. A model requests it with `TOOL:base32_encode:<text>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need deterministic Base32 handoffs.
- `base64`: encodes text to standard Base64 or decodes Base64 back to text
  (`operation: encode|decode`; default `encode`). Decoding validates the payload
  strictly and requires the decoded bytes to be valid UTF-8, so invalid Base64 or
  non-text payloads return a structured failure. A model requests it with
  `TOOL:base64:<text>`, giving agents a safe way to move opaque payloads between
  steps.
- `url_encode`: percent-encodes text via stdlib `urllib.parse.quote` (optional
  `safe` default `/`, `plus` for space-as-`+`). Empty, oversized, or invalid
  option requests return a structured failure. A model requests it with
  `TOOL:url_encode:<text>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 workers that need deterministic URL encoding.
- `url_parse`: splits an absolute URL into its components (scheme, host, port,
  path, query, grouped query parameters, fragment) using the standard library —
  never a network request. Relative URLs, empty input, and invalid ports return a
  structured failure. A model requests it with `TOOL:url_parse:<url>`, giving
  agents a safe way to route on a host or inspect a query parameter relayed by an
  earlier step.
- `uuid4`: generates random version-4 UUID identifier(s) (optional `count`
  requests it with `TOOL:yaml_to_json:enabled: true`, giving GPT-5.5 /
- `yaml_to_json`: converts a constrained safe YAML subset to canonical JSON
  1..16, default 1). Output is one UUID string or newline-joined UUIDs when
  `count` > 1. These are opaque identifiers for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 workflows — not cryptographic secrets or keying material.
  Out-of-range or non-integer `count` returns a structured failure. A model
  requests it with `TOOL:uuid4:`.
- `uuid5`: computes a deterministic version-5 UUID from a name and a namespace
  (`dns`, `url`, `oid`, `x500`, or a custom UUID string; default `dns`). Because
  a v5 UUID is a hash of `(namespace, name)`, the same inputs always yield the
  same id — keeping the runtime deterministic, unlike a random v4 UUID. Empty,
  oversized, or unusable-namespace requests return a structured failure. A model
  requests it with `TOOL:uuid5:<name>`, giving agents stable primary keys,
  idempotency keys, or correlation ids shared across steps.
- `slugify`: converts free-form text into a URL- and filesystem-safe ASCII slug.
  It strips diacritics, lowercases, collapses every run of non-alphanumeric
  characters into a single separator (default `-`, overridable), trims the ends,
  and can cap the length on a word boundary via `max_length`. Empty, oversized,
  unusable-separator, invalid-`max_length`, or slug-empty requests return a
  structured failure. A model requests it with `TOOL:slugify:<text>`, giving
  agents deterministic branch names, path segments, cache-file names, and anchor
  ids from arbitrary text.
- `datetime`: normalizes an ISO-8601 timestamp to a canonical UTC form
  (`YYYY-MM-DDTHH:MM:SS+00:00`) and reports its Unix epoch and weekday. A
  trailing `Z` (Zulu) designator and numeric offsets are both accepted; a naive
  timestamp fails unless `assume_utc=true` is passed. It reads no wall-clock
  `now`, so it stays fully deterministic. Empty, oversized, unparseable, or
  naive-without-`assume_utc` requests return a structured failure. A model
  requests it with `TOOL:datetime:<timestamp>`, giving agents one canonical
  instant to compare, sort, and log timestamps that arrive in mixed shapes.
- `duration`: parses an ISO-8601 duration (`PT1H30M`, `P1DT2H`, `P2W`, with an
  optional leading `-` and a fractional smallest component) into its total
  length in seconds plus a normalized component breakdown. Only fixed-length
  components (weeks, days, hours, minutes, seconds) are supported; calendar
  components (years/months) are refused because they have no fixed second
  length. It reads no wall-clock `now`, so it stays fully deterministic. Empty,
  oversized, calendar, componentless, or unparseable requests return a
  structured failure. A model requests it with `TOOL:duration:<duration>`,
  giving agents one exact scalar for retry backoffs, TTLs, and time budgets.
- `diff`: produces a deterministic unified diff between two texts via
  `difflib`. Supply sides as `text`+`other`, or as a single `text` split on the
  `<<<DIFF>>>` sentinel (so `TOOL:diff:...` still works with one payload).
  Optional `context` controls hunk size (default 3). Empty/oversized sides,
  ambiguous splits, and invalid context return a structured failure. Gives
  agents a trustworthy before/after comparison for observations and tool
  outputs — matching the gap popular agent frameworks fill with a dedicated
  diff/patch tool.
- `regex_replace`: applies a bounded regex find/replace (`text` / `pattern` /
  `repl`, optional `count`) via stdlib `re`. Empty or oversized input, patterns
  over 200 chars, nested-quantifier ReDoS shapes, and match counts over the
  cap return a structured failure. A model requests it with
  `TOOL:regex_replace:<text>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 workers that need deterministic substitutions before the next turn.
- `text_case`: converts text to `lower`, `upper`, `title`, `snake`, `kebab`, or `camel` (default `lower`; max 20_000 chars). Supply `text`+`case`, or a single payload split on `<<<TEXT_CASE>>>`. Empty, oversized, or unsupported `case` values return a structured failure. A model requests it with `TOOL:text_case:<text>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need deterministic case transforms.
- `text_indent`: indents every non-empty line by N spaces (default 2, max 32;
  optional `skip_first`). Supply `text`+`spaces`/`skip_first`, or a single
  payload split on `<<<TEXT_INDENT>>>`. Empty, oversized, or invalid option
  requests return a structured failure. A model requests it with
  `TOOL:text_indent:<text>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 workers that need deterministic indentation.
- `csv_select_columns`: selects and reorders CSV columns by name via stdlib `csv` (max 500 rows, 64 columns). Supply `text`+`columns`, or a single payload split on `<<<CSV_SELECT>>>`. Empty, oversized, malformed, unknown-column, or over-bounds requests return a structured failure. A model requests it with `TOOL:csv_select_columns:<csv><<<CSV_SELECT>>>col1,col2` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need deterministic tabular projection.
- `csv_unique`: deduplicates CSV rows by named column(s) via stdlib `csv`
  (keep first occurrence; max 500 rows, 64 columns). Supply `text`+`columns`,
  or a single payload split on `<<<CSV_UNIQUE>>>`. Empty, oversized, malformed,
  unknown-column, or over-bounds requests return a structured failure. A model
  requests it with `TOOL:csv_unique:<csv><<<CSV_UNIQUE>>>col1,col2` for
  GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need
  deterministic tabular deduplication.
- `csv_window`: emits sliding windows of CSV data rows with the header preserved once
  per window (`window_size` required; `step` default 1; optional `start_row`/`index`).
  It rejects malformed input and bounded-size violations for GPT-5.5 /
  Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
- `text_sort_lines`: sorts multi-line text ascending or descending (`order`
  default `asc`) with optional `unique` dedupe after sort. Empty, oversized, or
  unsupported-order requests return a structured failure. A model requests it
  with `TOOL:text_sort_lines:<text>`, giving agents a stable line order for
  checklists, tags, and other line-oriented observations.
- `unicode_normalize`: normalizes Unicode text via stdlib `unicodedata` to
  NFC (default), NFD, NFKC, or NFKD. Empty, oversized, or unsupported-form
  requests return a structured failure. A model requests it with
  `TOOL:unicode_normalize:<text>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini
  3.x / Kimi K2 workers that need canonical text before comparison or hashing.
- `text_wrap`: wraps or fills text via stdlib `textwrap` (`mode` `wrap` default
  or `fill`, `width` default 80). Empty, oversized, invalid-width, or
  unsupported-mode requests return a structured failure. A model requests it
  with `TOOL:text_wrap:<text>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 workers that need bounded line reflow for logs and previews.
- `html_attr_extract`: extracts HTML attribute values via stdlib
  `html.parser` (required `attr`; optional `tag` filter and `max_results`).
  Empty, oversized, or invalid-bound requests return a structured failure.
  A model requests it with `TOOL:html_attr_extract:<html>` for GPT-5.5 /
  Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need deterministic
  attribute extraction from markup handoffs.
- `html_entities`: encodes or decodes HTML entities via stdlib `html`
  (`mode` `encode` default or `decode`; encode optionally escapes quotes).
  Empty, oversized, unsupported-mode, or invalid-quote requests return a
  structured failure. A model requests it with `TOOL:html_entities:<text>`
  for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need
  deterministic entity escaping before render or compare.
- `html_strip`: strips HTML markup to plain text via the stdlib HTML parser.
  Documents containing `<script>` or `<style>` are rejected; empty or oversized
  input returns a structured failure. A model requests it with
  `TOOL:html_strip:<html>`, giving agents a deterministic way to turn scraped
  snippets into readable text without inventing or leaking markup.
- `html_markdown`: converts safe HTML fragments to Markdown (headings, links,
  lists, bold/italic, code, paragraphs) via stdlib `html.parser`. Documents
  containing `<script>` or `<style>` are rejected; empty or oversized input
  returns a structured failure. A model requests it with
  `TOOL:html_markdown:<html>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 workers that need deterministic HTML→Markdown handoffs.
- `html_table`: extracts the first HTML table, or a 1-based `table_index`, and
  renders it as GitHub-flavored markdown or CSV. It uses stdlib `html.parser`
  only, rejects `<script>`/`<style>`, caps document/output chars plus rows and
  columns, and returns structured metadata for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 workers that need safe tabular observations from HTML.
- `html_table_csv`: converts the first HTML table (default) or every table
  (`all=true`) to CSV text via stdlib `html.parser`. It rejects `<script>`/
  `<style>`, caps document and output chars, and returns structured failures for
  empty, oversized, or table-less input. A model requests it with
  `TOOL:html_table_csv:<html>` for deterministic CSV handoffs across GPT-5.5 /
  Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
- `mime_attachment_names`, `text_outdent`: parses bounded raw MIME with stdlib `email` and
  returns only a JSON list of decoded attachment `filename`/`name` parameters.
  Empty, oversized, or defective input returns a structured failure; payloads
  are never returned or written. A model requests it with
  `TOOL:mime_attachment_names:<raw>` for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 workers that need safe attachment routing metadata.
- `mime_attachment_sizes`: parses bounded raw MIME with stdlib `email` and
  returns only a JSON list of attachment `filename`/`size` objects. Sizes use
  `Content-Length` when present, otherwise decoded payload byte length.
  Payloads are never returned or written. A model requests it with
  `TOOL:mime_attachment_sizes:<raw>` for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 workers that need safe attachment size metadata.
- `mime_attachment_cid_map`: parses bounded raw MIME and returns a JSON map of Content-ID
  tokens to attachment `filename`/`content_type` objects without payloads. A model
  requests it with `TOOL:mime_attachment_cid_map:<raw>` for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 workers.
- `mime_attachment_disposition`: parses bounded raw MIME with stdlib `email`
  and returns only Content-Disposition `filename`/`disposition` objects for
  attachment and inline parts, including unnamed disposition records. Payloads
  are never returned or written. Empty, oversized, or defective input returns a
  structured failure. A model requests it with
  `TOOL:mime_attachment_disposition:<raw>` for GPT-5.5 /
  Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need safe routing
  metadata without attachment content.
- `mime_attachment_encoding`: parses bounded raw MIME and returns only named
- `mime_attachment_filenames_unique`: maps duplicate MIME attachment filenames to unique names (`file-2.pdf`); no payloads. A model requests it with `TOOL:mime_attachment_filenames_unique:<raw>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
  attachment `filename`/`encoding` objects. Content-Transfer-Encoding tokens
  are normalized, missing values default to `7bit`, and payloads are never
  decoded or returned. A model requests it with
  `TOOL:mime_attachment_encoding:<raw>` for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 workers.
- `mime_multipart`: parses a raw MIME message via stdlib `email` and returns
  JSON summaries of each part (`content_type`, `charset`, `size`, `payload
  preview`). Empty or oversized input returns a structured failure. A model
  requests it with `TOOL:mime_multipart:<raw>` for GPT-5.5 / Claude Sonnet
  4.6 / Gemini 3.x / Kimi K2 workers that need part metadata before parsing
  attachments.
- `template_render`: fills simple `{var}` or Jinja-like `{{ var }}`
  placeholders from scalar JSON variables. It HTML-escapes every substituted
  value, rejects expressions/filters/attribute access instead of evaluating
  them, caps template/variable/output sizes, and supports a single directive
  payload split on `<<<TEMPLATE_VARS>>>`. A model requests it with
  `TOOL:template_render:Hello {name}<<<TEMPLATE_VARS>>>{"name":"Ada"}` for safe,
  repeatable snippets without raw string surgery.
- `zip_list`: lists ZIP archive member metadata (`name`, `size`, `compress_size`,
  `date`) from base64-encoded bytes via stdlib `zipfile`. It never extracts or
  executes archive members; invalid base64, non-ZIP payloads, and empty or
  oversized input return structured failures. A model requests it with
  `TOOL:zip_list:<base64>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi
  K2 workers inspecting small attachment bundles.

## More tool notes

- `json_diff_paths`: compares two bounded JSON documents and returns only the
  sorted paths whose values differ, using dotted object keys and bracketed array
  indexes. Supply `text`+`other`, or one directive payload split on
  `<<<JSON_DIFF_PATHS>>>`. Empty, malformed, non-finite, oversized, or
  over-expanded input returns a structured failure. A model requests it with
  `TOOL:json_diff_paths:<before><<<JSON_DIFF_PATHS>>><after>` for GPT-5.5 /
  Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need compact change
  routing without echoing both documents.

- `json_patch_apply`: applies bounded RFC 6902 JSON Patch arrays with
  `add`/`remove`/`replace`/`move`/`copy`/`test` operations via stdlib only.
  Supply `text`+`patch`, or split one directive payload on `<<<JSON_PATCH>>>`;
  documents are capped at 20,000 characters and patches at 200 operations for
  GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

- `text_justify_lines`: formats bounded non-empty lines with left, right,
  center, or full justification at widths up to 500 while preserving line
  endings and never truncating content. It supports `text` options or the
  `<<<TEXT_JUSTIFY_LINES>>>` sentinel for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 workers.

- `text_slug_lines`: slugifies every bounded document line independently while
  preserving original line endings. It supports configurable separators,
  casing, empty-line handling, and the `<<<TEXT_SLUG_LINES>>>` sentinel for
  GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

- `text_title_lines`: title-cases every bounded document line independently while
  preserving original line endings. It supports `skip_empty`, `lowercase_first`, and the
  `<<<TEXT_TITLE_LINES>>>` sentinel for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 workers.

- `text_margin_lines`: adds left/right ASCII margins to non-empty lines for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

- `mime_multipart_flatten`: recursively flattens nested multipart MIME via
  stdlib `email` into a JSON array of leaf-part metadata (`content_type`,
  `filename`, `content_id`, `size`, `depth`), max 20_000 chars and 200 leaf
  parts. Payload bytes are never returned. Empty, oversized, or malformed
  input returns a structured failure. A model requests it with
  `TOOL:mime_multipart_flatten:<raw>` for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 workers that need a safe inventory of nested email
  parts, inspired by mail pipelines in popular agent frameworks.

- `html_links_extract`: extracts HTML anchor `href`+`text` pairs as compact
- `semver_compare`: compares two semantic versions (`major.minor.patch` with optional pre-release) and returns `-1`/`0`/`1` plus a human relation. Supply `version_a`+`version_b`, or a payload split on `<<<SEMVER_COMPARE>>>`. Empty or invalid versions return a structured failure. A model requests it with `TOOL:semver_compare:<a><<<SEMVER_COMPARE>>><b>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need deterministic version gating.
- `csv_fillna`: fills empty CSV cells with a constant via stdlib `csv` (`fill_value` default empty string; optional `columns` subset). Supply `text`+`fill_value`, or a payload split on `<<<CSV_FILLNA>>>` (optional `<<<COLUMNS>>>col1,col2`). Empty, oversized, malformed, unknown-column, or over-bounds requests return a structured failure. A model requests it with `TOOL:csv_fillna:<csv>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need deterministic tabular fillna.
  JSON via stdlib `html.parser` (`max_links` default 100, range 1..500).
  Documents containing `script`/`style` are rejected. Empty, link-less,
  oversized, or invalid `max_links` requests return a structured failure. A
  model requests it with `TOOL:html_links_extract:<html>` for GPT-5.5 /
  Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 research workers.
- `ics_parse`: parses iCalendar (`.ics`) text and extracts VEVENT `SUMMARY`/`DTSTART`/`DTEND`/`UID`/`LOCATION` as JSON Lines via stdlib only (max 20_000 chars, 100 events). Empty, oversized, or VEVENT-less requests return a structured failure. A model requests it with `TOOL:ics_parse:<ics>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need deterministic calendar field extraction.
- `markdown_toc`: builds a nested Markdown table of contents from ATX
  headings (`#`..`######`) up to `max_level` (default 3, range 1..6) with
  GitHub-like slug anchors. Supply `text`+`max_level`, or a payload split on
  `<<<MARKDOWN_TOC>>>`. Empty, heading-less, oversized, or invalid `max_level`
  requests return a structured failure. A model requests it with
  `TOOL:markdown_toc:<markdown>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 documentation workers.
- `text_unique_lines`: deduplicates lines in first-seen order (optional `strip`,
  default true) while preserving original line endings. Supply `text`+`strip`,
  or a single payload split on `<<<TEXT_UNIQUE_LINES>>>`. Empty, oversized, or
  invalid `strip` requests return a structured failure. A model requests it with
  `TOOL:text_unique_lines:<text>` for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 workers that need stable dedupe without sorting.
- `text_collapse_blank`: collapses runs of consecutive blank or
  whitespace-only lines to at most `max_blank` lines (default 1, range
  0..100) while preserving non-blank line endings. Supply `text`+`max_blank`,
  or a single payload split on `<<<TEXT_COLLAPSE_BLANK>>>`. Empty, oversized,
  or invalid `max_blank` requests return a structured failure. A model
  requests it with `TOOL:text_collapse_blank:<text>` for GPT-5.5 / Claude
  Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need to tidy noisy blank-line
  runs before the next turn.

## Guide index (former README list)

- [MCP Tool Bridge Guide](../docs/guides/MCP_TOOLS_GUIDE.md)
- [Typed Bot Handoff Guide](../docs/guides/BOT_HANDOFF_GUIDE.md)
- [HITL Approval Gate Guide](../docs/guides/HITL_APPROVAL_GATE_GUIDE.md)
- [Parallel Fan-Out Guide](../docs/guides/PARALLEL_FANOUT_GUIDE.md)
- [Text Margin Lines Tool Guide](../docs/guides/TEXT_MARGIN_LINES_TOOL_GUIDE.md)

- [Quickstart](../docs/QUICKSTART.md)
- [Configuration](../docs/CONFIGURATION.md)
- [Content Type Sniff Tool Guide](../docs/guides/CONTENT_TYPE_SNIFF_TOOL_GUIDE.md)
- [Cron Next Tool Guide](../docs/guides/CRON_NEXT_TOOL_GUIDE.md)
- [Safety](../docs/SAFETY.md)
- [Architecture](../docs/ARCHITECTURE.md)
- [JSON Path Tool Guide](../docs/guides/JSON_PATH_TOOL_GUIDE.md)
- [JSON Query Tool Guide](../docs/guides/JSON_QUERY_TOOL_GUIDE.md)
- [JWT Decode Tool Guide](../docs/guides/JWT_DECODE_TOOL_GUIDE.md)
- [Hex Encode Tool Guide](../docs/guides/HEX_ENCODE_TOOL_GUIDE.md)
- [URL Encode Tool Guide](../docs/guides/URL_ENCODE_TOOL_GUIDE.md)
- [JSON Merge Patch Tool Guide](../docs/guides/JSON_MERGE_PATCH_TOOL_GUIDE.md)
- [Spreadsheet Slice Tool Guide](../docs/guides/SPREADSHEET_SLICE_TOOL_GUIDE.md)
- [HTML Attribute Extract Tool Guide](../docs/guides/HTML_ATTR_EXTRACT_TOOL_GUIDE.md)
- [HTML Entities Tool Guide](../docs/guides/HTML_ENTITIES_TOOL_GUIDE.md)
- [HTML Markdown Tool Guide](../docs/guides/HTML_MARKDOWN_TOOL_GUIDE.md)
- [HTML Table Tool Guide](../docs/guides/HTML_TABLE_TOOL_GUIDE.md)
- [HTML Table CSV Tool Guide](../docs/guides/HTML_TABLE_CSV_TOOL_GUIDE.md)
- [ICS Parse Tool Guide](../docs/guides/ICS_PARSE_TOOL_GUIDE.md)
- [MIME Attachment CID Map Tool Guide](../docs/guides/MIME_ATTACHMENT_CID_MAP_TOOL_GUIDE.md)
- [MIME Attachment Names Tool Guide](../docs/guides/MIME_ATTACHMENT_NAMES_TOOL_GUIDE.md)
- [MIME Attachment Disposition Tool Guide](../docs/guides/MIME_ATTACHMENT_DISPOSITION_TOOL_GUIDE.md)
- [MIME Multipart Tool Guide](../docs/guides/MIME_MULTIPART_TOOL_GUIDE.md)
- [Template Render Tool Guide](../docs/guides/TEMPLATE_RENDER_TOOL_GUIDE.md)
- [TOML Format Tool Guide](../docs/guides/TOML_FORMAT_TOOL_GUIDE.md)
- [TSV Format Tool Guide](../docs/guides/TSV_FORMAT_TOOL_GUIDE.md)
- [Text Title Lines Tool Guide](../docs/guides/TEXT_TITLE_LINES_TOOL_GUIDE.md)
- [Text Sort Lines Tool Guide](../docs/guides/TEXT_SORT_LINES_TOOL_GUIDE.md)
- [Text Squeeze Whitespace Tool Guide](../docs/guides/TEXT_SQUEEZE_WS_TOOL_GUIDE.md)
- [Text Indent Tool Guide](../docs/guides/TEXT_INDENT_TOOL_GUIDE.md)
- [Text Case Tool Guide](../docs/guides/TEXT_CASE_TOOL_GUIDE.md)
- [CSV Select Columns Tool Guide](../docs/guides/CSV_SELECT_COLUMNS_TOOL_GUIDE.md)
- [CSV Sort Tool Guide](../docs/guides/CSV_SORT_TOOL_GUIDE.md)
- [CSV Unique Tool Guide](../docs/guides/CSV_UNIQUE_TOOL_GUIDE.md)
- [CSV Window Tool Guide](../docs/guides/CSV_WINDOW_TOOL_GUIDE.md)
- [Unicode Normalize Tool Guide](../docs/guides/UNICODE_NORMALIZE_TOOL_GUIDE.md)
- [UUID4 Tool Guide](../docs/guides/UUID4_TOOL_GUIDE.md)
- [Text Wrap Tool Guide](../docs/guides/TEXT_WRAP_TOOL_GUIDE.md)
- [Line Number Tool Guide](../docs/guides/LINE_NUMBER_TOOL_GUIDE.md)
- [Regex Replace Tool Guide](../docs/guides/REGEX_REPLACE_TOOL_GUIDE.md)
- [CSV Filter Tool Guide](../docs/guides/CSV_FILTER_TOOL_GUIDE.md)
- [CSV Group-By Tool Guide](../docs/guides/CSV_GROUPBY_TOOL_GUIDE.md)
- [CSV Join Tool Guide](../docs/guides/CSV_JOIN_TOOL_GUIDE.md)
- [CSV Pivot Tool Guide](../docs/guides/CSV_PIVOT_TOOL_GUIDE.md)
- [CSV TSV Tool Guide](../docs/guides/CSV_TSV_TOOL_GUIDE.md)
- [YAML Format Tool Guide](../docs/guides/YAML_FORMAT_TOOL_GUIDE.md)
- [ZIP List Tool Guide](../docs/guides/ZIP_LIST_TOOL_GUIDE.md)
