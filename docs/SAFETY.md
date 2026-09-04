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
- `cron_next`: parses a 5-field cron expression and returns the next N UTC fire times as ISO-8601 lines (`count` default 5 max 20; optional `from_iso`); rejects invalid fields; stdlib only (no `croniter`); never executes code or makes network requests.
- `crc32`
- `csv_to_json`: returns unsigned CRC32 hex digest of UTF-8 `text` (max 100_000 chars); never executes code or makes network requests.
- `echo`: safe deterministic echo tool for demos.
- `hmac_sign`: computes an HMAC digest of text with a secret key (`sha256` default, `sha1`, `sha512`; output `hex` or `base64`); max text 20_000 / key 1_024 chars; never logs the secret; never executes code or makes network requests.
- `isbn13`: validate an ISBN-13 (EAN-13) digit string or append a check digit (`mode`: `validate` default or `check_digit`; `text` or `isbn`; spaces/dashes stripped; max 2000 chars); rejects empty/non-digit/oversized/invalid mode; never executes code or makes network requests.
- `jsonl_parse`: parses JSON Lines into a pretty JSON array (`mode`: `objects` default or `any`; max 500 lines / 20_000 chars); rejects blank/invalid lines and non-objects in objects mode; never executes code or makes network requests.
- `readonly_file`: root-contained read-only file access.
- `caesar_cipher`: applies a Caesar cipher shift to text (default shift 13); preserves upper/lower case; non-alpha chars pass through; max 20_000 chars; rejects empty/oversized/invalid shift; never executes code or makes network requests.
- `calculator`: sandboxed AST arithmetic; refuses non-real and non-finite results, bounds the exponent, and rejects results whose integer magnitude exceeds a fixed bit bound (stops nested power towers).
- `json_format`: JSON validation and canonicalization.
- `json_merge_patch`: applies RFC 7396 JSON Merge Patch via stdlib `json`; rejects empty/oversized/malformed input and over-deep merges; never executes code or makes network requests.
- `text_outdent` — remove up to N leading spaces per non-empty line
- `uuid_nil`: returns the RFC 4122 nil UUID `00000000-0000-0000-0000-000000000000` (or max UUID when `mode=max`); never executes code or makes network requests.
- `ini_parse`: parses INI/CFG text into pretty JSON sections→keys via stdlib `configparser` (max 20_000 chars); never executes code or makes network requests.
- `url_normalize`: normalizes a URL (lowercase scheme/host, drop default ports/fragments; optional `strip_trailing_slash`); never executes code or makes network requests.
- `levenshtein`: returns classic Levenshtein edit distance between `a` and `b` (max 2000 chars each); never executes code or makes network requests.
- `yaml_format`: validates and canonicalizes a constrained YAML subset (block mappings/sequences, JSON-style flow collections, scalar values); rejects anchors, aliases, tags, document markers, constructors, malformed indentation, oversized input, and non-finite numbers; never executes code.
- `zip_list`: lists ZIP archive member metadata (`name`, `size`, `compress_size`, `date`) from base64-encoded bytes via stdlib `zipfile`; rejects empty/oversized input, invalid base64, and non-ZIP payloads; never extracts or executes archive members.
- `toml_format`: validates TOML via `tomllib` (Python 3.11+) or `tomli` when available and returns a deterministic serialization (sorted keys; tables/arrays/strings/ints/floats/bools); rejects empty/oversized input, dates/times, non-finite floats, and missing parsers; never executes code.
- `toml_json`: converts between TOML and JSON text (`direction`: `to_json` default or `to_toml`); uses the same portable dict/list/str/int/float/bool subset as `toml_format`/`json_format`; rejects empty/oversized input, dates/times, JSON null, non-finite numbers, and missing parsers; never executes code.
- `tsv_format`: validates tab-separated values via stdlib `csv` (`excel-tab` dialect) and returns canonical TSV with consistent newlines; rejects empty/oversized input, uneven column counts (header defines width), and trailing blank rows are stripped; never executes code.
- `line_number`: prefixes each text line with a 1-based line number (optional `start`/`separator`); rejects empty/oversized input and invalid start/separator; never executes code or makes network requests.
- `csv_filter`: filters CSV rows by a named column predicate via stdlib `csv` (`mode`: `equals` default or `contains`; `case_insensitive`: true default); rejects empty/oversized/malformed input, unknown columns, and row/column overages; never executes code or makes network requests.
- `csv_groupby`: groups CSV rows by key columns and aggregates numeric value columns via stdlib `csv` (`agg`: `sum` default, `count`, `min`, `max`, `mean`); rejects empty/oversized/malformed input, unknown columns, and non-numeric values; never executes code or makes network requests.
- `csv_join`: joins two CSV tables on a key column via stdlib `csv` (`how`: `inner` default or `left`; `on` or `left_on`+`right_on`); rejects empty/oversized/malformed input and unknown columns; never executes code or makes network requests.
- `csv_select_columns`: selects/reorders CSV columns by name via stdlib `csv` (`text`+`columns`, or `<<<CSV_SELECT>>>`); rejects empty/oversized/malformed input, unknown/duplicate columns, and row/column overages (max 500 rows, 64 columns); never executes code or makes network requests.
- `csv_pivot`: pivots long CSV to wide or unpivots via stdlib `csv` (`mode`: `pivot` default or `unpivot`); rejects empty/oversized/malformed input and unknown columns; never executes code or makes network requests.
- `csv_stack`: vertically concatenates at least two CSV documents with identical non-empty unique headers (`csvs` list or `text` split by `<<<CSV_STACK>>>`); rejects empty/oversized/malformed input, mismatched headers, uneven rows, and output over 500 rows or 64 columns; never executes code or makes network requests.
- `csv_tsv`: converts between CSV and TSV text (`direction`: `csv_to_tsv` default or `tsv_to_csv`); optional single-character input `delimiter` override; rejects empty/oversized input, invalid direction/delimiter, uneven column counts, and malformed tables; never executes code.
- `csv_transpose`: transposes CSV rows into columns (pads short rows; max 20_000 chars / 500 rows / 64 columns); rejects empty/malformed/oversized input; never executes code or makes network requests.
- `html_attr_extract`: extracts HTML attribute values via stdlib `html.parser` (required `attr`; optional `tag` filter and `max_results`); rejects empty/oversized input and invalid bounds; never executes code or makes network requests.
- `ics_parse`: parses iCalendar (`.ics`) VEVENT blocks via stdlib only and returns JSON Lines with SUMMARY/DTSTART/DTEND/UID/LOCATION (max 20_000 chars, 100 events); rejects empty/oversized/VEVENT-less input; never executes code or makes network requests.
- `semver_compare`: compares two SemVer versions (`major.minor.patch` with optional pre-release; build metadata ignored) and returns `-1`/`0`/`1` plus a human relation (`version_a`+`version_b` or `<<<SEMVER_COMPARE>>>`); rejects empty/invalid versions; never executes code or makes network requests.
- `metaphone`
- `base32_encode`: encodes or decodes text via stdlib `base64.b32encode`/`b32decode` (`mode`: `encode` default or `decode`; standard alphabet; max 20_000 chars); rejects empty/oversized/invalid input; never executes code or makes network requests.
- `base58`: encodes or decodes text via Bitcoin-alphabet Base58 (`mode`: `encode` default or `decode`; `text` or `data`; max 20_000 chars); rejects empty/oversized/invalid input; never executes code or makes network requests.
- `base64`: encodes text to Base64 or decodes Base64 to text (encode|decode; default encode).
- `base85`: encodes or decodes text via Adobe ASCII85/Base85 (`mode`: `encode` default or `decode`; `text` or `data`; max 20_000 chars); rejects empty/oversized/invalid input; never executes code or makes network requests.
- `csv`: parses CSV text into canonical JSON (header + rows); caps rows/columns; optional single-character `delimiter`; never executes code.
- `csv_fillna`: fills empty CSV cells with a constant via stdlib `csv` (`fill_value` default empty string; optional `columns` subset; accepts `<<<CSV_FILLNA>>>`); rejects empty/oversized/malformed input, unknown columns, and row/column overages (max 500 rows, 64 columns); never executes code or makes network requests.
- `csv_sort`: sorts CSV rows by a named column via stdlib `csv` while keeping the header (`text`+`column`, optional `descending`/`numeric`, or `<<<CSV_SORT>>>`); rejects empty/oversized/malformed input, missing/duplicate headers, unknown columns, and row/column overages; never executes code or makes network requests.
- `csv_unique`: deduplicates CSV rows by named column(s) via stdlib `csv`, keeping the first occurrence and header (`text`+`columns`, or `<<<CSV_UNIQUE>>>`); rejects empty/oversized/malformed input, missing/duplicate headers, unknown columns, and row/column overages; never executes code or makes network requests.
- `csv_window`: emits sliding CSV row windows with the header preserved once per window (`window_size` required; `step` default 1; `start_row` default 0; optional `index`); rejects empty/oversized/malformed input and row/column overages; never executes code or makes network requests.
- `datetime`: normalizes an ISO-8601 timestamp to canonical UTC (with epoch and weekday); reads no wall-clock `now` and requires `assume_utc` for naive input.
- `diff`: produces a unified diff between two texts (`text`+`other`, or `text` split on `<<<DIFF>>>` with or without surrounding newlines); bounds each side and the output line count; never executes code.
- `duration`: parses an ISO-8601 duration into total seconds and a component breakdown; supports only fixed-length components (weeks/days/hours/minutes/seconds) and refuses calendar years/months; designators are case-insensitive (`pt1h30m` == `PT1H30M`); reads no wall-clock `now`.
- `hash`: computes a hex digest of text (md5, sha1, sha256, sha512; default sha256).
- `hex_encode`: encodes text to a hexadecimal string of its UTF-8 bytes (`text` plus optional `uppercase`, default false, or `<<<HEX_ENCODE>>>`); rejects empty/oversized input and invalid boolean settings; never executes code or makes network requests.
- `html_entities`: encodes or decodes HTML entities via stdlib `html` (`mode`: `encode` default or `decode`; encode optionally escapes quotes); rejects empty/oversized input, unsupported mode, and invalid quote; never executes code or makes network requests.
- `html_links_extract`: extracts HTML anchor href+text pairs as JSON (`max_links` default 100); rejects script/style and empty/link-less/oversized/invalid input; never executes code or makes network requests.
- `html_markdown`: converts safe HTML fragments to Markdown (headings, links, lists, bold/italic, code, paragraphs) via stdlib `html.parser`; rejects documents containing `script`/`style`; empty or oversized input returns `ok=False`; never executes code or makes network requests.
- `html_strip`: strips HTML tags to plain text via stdlib `html.parser`; rejects documents containing `script`/`style`; empty or oversized input returns `ok=False`; never executes code.
- `html_table_csv`: converts the first HTML table (default) or all tables (`all=true`) to CSV text via stdlib `html.parser`; rejects documents containing `script`/`style`; empty, oversized, or table-less input returns `ok=False`; never executes code or makes network requests.
- `iban_check`: validates an IBAN string using the ISO 13616 mod-97 algorithm (`iban` or `text`; strips spaces/dashes; max 2000 chars); returns valid/invalid plus country code; rejects empty/oversized/structurally invalid input; never executes code or makes network requests.
- `json_path`: extracts values from JSON via a simple dot/[index] path (`text`+`path`, or `text` split on `<<<JSON_PATH>>>`); rejects recursive descent, filters, scripts, pipes, oversized input/results, and invalid JSON; never executes code.
- `json_pointer`: extracts values from JSON via RFC 6901 JSON Pointer (`text`+`pointer`, or `text` split on `<<<JSON_POINTER>>>`; empty pointer = whole document; `~0`/`~1` escapes); rejects invalid pointers, missing keys, bad array indexes, oversized input/results, and invalid JSON; never executes code.
- `json_query`: filters JSON object arrays (`where` field==value) or plucks a field (`pluck`) via stdlib `json`; rejects empty/oversized/malformed input and unsupported mode; never executes code, evaluates scripts, or makes network requests.
- `jwt_decode, jwt_encode`: base64url-decodes JWT header+payload into JSON claims; **never verifies signatures or trusts claims**; rejects empty/oversized/malformed tokens; never executes code or makes network requests.
- `luhn`: validate a digit string with Luhn or append a check digit (`mode`: `validate` default or `check_digit`; `text` or `number`; spaces/dashes stripped; max 2000 chars); rejects empty/non-digit/oversized/invalid mode; never executes code or makes network requests.
- `markdown_table`: renders CSV-like text or list-of-rows input as a GitHub-flavored markdown table; caps rows/columns; escapes pipe/newline cell content; never executes code.
- `markdown_toc`: builds a nested Markdown TOC from ATX headings up to `max_level` (default 3; accepts `<<<MARKDOWN_TOC>>>`); rejects empty/heading-less/oversized/invalid input; never executes code or makes network requests.
- `mime_attachment_names`: parses a raw MIME message via stdlib `email` and returns only a JSON list of decoded `filename`/`name` parameters; rejects empty/oversized/malformed input; never returns payloads, executes code, writes attachments, or makes network requests.
- `mime_attachment_sizes`: parses a raw MIME message via stdlib `email` and returns only a JSON list of decoded attachment `filename`/`name` parameters with byte sizes (`Content-Length` when present, otherwise decoded payload length); rejects empty/oversized/malformed input; never returns payloads, executes code, writes attachments, or makes network requests.
- `mime_multipart`: parses a raw MIME message via stdlib `email` and returns JSON summaries of each part (`content_type`, `charset`, `size`, `payload_preview`); rejects empty/oversized input; never executes code, extracts attachments to disk, or makes network requests.
- `mime_multipart_flatten`: recursively flattens nested multipart MIME into leaf metadata JSON (`content_type`, `filename`, `content_id`, `size`, `depth`) without payloads; rejects empty/oversized input; never executes code or makes network requests.
- `mime_part_headers`: parses a raw MIME message via stdlib `email` and returns only top-level and per-part header name/value maps; rejects empty/oversized/malformed input; never returns payloads, executes code, writes attachments, or makes network requests.
- `morse`: encode or decode International Morse (`mode`: `encode` default or `decode`; `text` or `data`; letter gap space, word gap ` / `; max 20_000 chars); rejects empty/oversized/invalid tokens; never executes code or makes network requests.
- `nato_phonetic`: encode text to NATO phonetic alphabet or decode phonetic words back to text (`mode`: `encode` default or `decode`; `text`; max 2000 chars); non-alpha/digit chars pass through; rejects empty/oversized/invalid mode; never executes code or makes network requests.
- `pluralize`: pluralize or singularize a single English word (`mode`: `pluralize` default or `singularize`; `text` or `word`; max 2000 chars); rejects empty/multi-word/oversized/invalid mode; never executes code or makes network requests.
- `punycode`: encode or decode domain text via Punycode/IDNA (`mode`: `encode` default or `decode`; `text` or `domain`; max 2000 chars); rejects empty/oversized/invalid input; never executes code or makes network requests.
- `redact`: scrubs PII (email, phone, SSN, IPv4, IPv6) from text into typed placeholders.
- `regex`: extracts regex matches from text (`text`+`pattern`, or `text` split on `<<<REGEX>>>`); returns canonical JSON of spans/groups; bounds document/pattern size and match count; never executes code.
- `regex_replace`: applies a bounded regex find/replace (`text`/`pattern`/`repl`, optional `count`); rejects oversized documents/patterns, nested-quantifier ReDoS shapes, and match counts over the cap; never executes code or makes network requests.
- `rot13`: apply ROT13 to text (`text` or `data`; max 20_000 chars; self-inverse); rejects empty/oversized/missing input; never executes code or makes network requests.
- `slugify`: converts text into a URL-safe ASCII slug (separator default `-`, optional `max_length` truncated on a word boundary).
- `soundex`: returns American Soundex phonetic code for `text` (max 2000 chars); 4-character code; never executes code or makes network requests.
- `template_render`: renders `{var}` / `{{ var }}` placeholders from scalar JSON variables (`template`+`variables`, or `text` split on `<<<TEMPLATE_VARS>>>`); HTML-escapes substitutions; rejects expressions, filters, attribute lookup, unsupported brace syntax, nested variables, and oversized output; never executes code.
- `text_case`: converts text case via stdlib helpers (`case`: `lower` default, `upper`, `title`, `snake`, `kebab`, `camel`; `text`+`case` or `<<<TEXT_CASE>>>`); rejects empty/oversized input and unsupported cases; never executes code or makes network requests.
- `text_collapse_blank`: collapses consecutive blank/whitespace-only lines to at most `max_blank` blank lines (default 1; accepts `<<<TEXT_COLLAPSE_BLANK>>>`); rejects empty/oversized/invalid input; never executes code or makes network requests.
- `text_dedent`: removes common leading whitespace via stdlib `textwrap.dedent` (`text` plus optional `strip`, default true, or `<<<TEXT_DEDENT>>>`); rejects empty/oversized input and invalid boolean settings; never executes code or makes network requests.
- `text_indent`: indents every non-empty line by N spaces (`text` plus optional `spaces` default 2 max 32 and `skip_first` default false, or `<<<TEXT_INDENT>>>`); rejects empty/oversized input and invalid options; never executes code or makes network requests.
- `text_sort_lines`: sorts text lines ascending or descending (`order`: `asc`/`desc`, default `asc`); optional `unique` dedupe after sort; rejects empty/oversized input and unsupported order; never executes code.
- `text_squeeze_ws`: collapses whitespace runs to a single space (`text` plus optional `preserve_newlines`, default false, or `<<<TEXT_SQUEEZE>>>`); when `preserve_newlines` is true only horizontal whitespace within lines is squeezed; rejects empty/oversized input and invalid boolean settings; never executes code or makes network requests.
- `text_wrap`: wraps or fills text via stdlib `textwrap` (`mode`: `wrap` default or `fill`, `width` default 80, range 1..500); rejects empty/oversized input, invalid width, and unsupported mode; never executes code or makes network requests.
- `truncate`: truncates text to a max length (`max_length` arg, or `text` split on `<<<TRUNCATE>>>`, default 256); optional custom `ellipsis`; bounds input size; never executes code.
- `unicode_normalize`: normalizes Unicode text via stdlib `unicodedata` (`form`: NFC default, NFD, NFKC, NFKD); rejects empty/oversized input and unsupported forms; never executes code or makes network requests.
- `url_encode`: percent-encodes text via stdlib `urllib.parse.quote` (`text` plus optional `safe` default `/` and `plus` default false, or `<<<URL_ENCODE>>>`); rejects empty/oversized input and invalid boolean settings; never executes code or makes network requests.
- `url_parse`: splits an absolute URL into scheme, host, port, path, query, and fragment.
- `uuid4`: generates random version-4 UUID identifier(s) (optional `count` 1..16, default 1); opaque ids only — not cryptographic secrets; never executes code or makes network requests.
- `uuid5`: computes a deterministic version-5 UUID from a name and namespace (dns|url|oid|x500|custom UUID; default dns).
- `xml_escape`: escapes or unescapes XML special characters via stdlib `xml.sax.saxutils` (`mode`: `escape` default or `unescape`; max 20_000 chars); rejects empty/oversized/unsupported-mode input; never executes code or makes network requests.
- `xml_parse`: parses XML via stdlib `xml.etree.ElementTree` into a compact indented text tree (tags, `@attr=value`, text nodes); rejects empty/oversized input, DOCTYPE/ENTITY declarations (XXE hardening), and malformed XML; depth- and element-capped rendering; never executes code.

Unknown tools are rejected by `SafetyPolicy.validate_tool()`.

## Cancellation

Set `MULTIBOT_CANCEL_FILE=/path/to/cancel`. If that file exists before the next action, the run transitions to `cancelled` and persists a `run_cancelled` event.

## Provider Credentials

Credentials are read from environment variables and are never written to the event log. Event payloads store normalized provider output text and metadata, not secret values.

## Known Limits

This repo does not expose a network service or remote terminal control. If adapted into a server, add authentication, authorization, request auditing, workspace isolation, and per-user quota enforcement before exposing it beyond localhost.
- `yaml_to_json`: converts a constrained safe YAML subset to canonical JSON (sorted keys, 2-space indent) via the same stdlib-only subset parser as `yaml_format` (no PyYAML); rejects anchors, aliases, tags, constructors, oversized input/results, and non-finite numbers; never executes code.
- `csv_diff`: compares two CSV documents by one or more primary-key columns via stdlib `csv` and returns JSON key maps for added, removed, and changed rows (`left`+`right`+`key`, or `<<<CSV_DIFF>>>`/`<<<CSV_DIFF_KEY>>>`); rejects empty/oversized/malformed input, missing/duplicate/empty keys, and row/column overages; never executes code or makes network requests.
- `json_flatten`: flattens nested JSON objects/arrays into dotted/bracket keys via stdlib `json` (optional `separator` default `.`; max 20_000 chars input, 2000 keys); rejects empty/oversized/malformed/over-expanded input; never executes code or makes network requests.
- `json_diff_paths`: compares two JSON documents via stdlib `json` and returns only sorted differing paths in dotted/bracket notation (`text`+`other`, or `<<<JSON_DIFF_PATHS>>>`; max 20_000 chars per document, 2000 paths); rejects empty, oversized, malformed, non-finite, ambiguous, over-expanded, or oversized-output requests; never executes code or makes network requests.
- `json_patch_apply`: applies up to 200 RFC 6902 `add`/`remove`/`replace`/`move`/`copy`/`test` operations to bounded JSON (`text`+`patch`, or `<<<JSON_PATCH>>>`) via stdlib only; validates RFC 6901 paths, finite JSON, array bounds, and output size; never executes code or makes network requests.
- `json_unflatten`: rebuilds nested JSON objects/arrays from dotted/bracket flat keys via stdlib `json` (optional `separator` default `.`; max 20_000 chars input, 2000 keys); rejects empty/oversized/malformed/non-object input and conflicting paths; never executes code or makes network requests.
- `text_center_lines`: centers each non-empty line to a target width with leading/trailing ASCII spaces (`width` default 80 range 1..200; optional `skip_first`; accepts `<<<TEXT_CENTER_LINES>>>`); rejects empty/oversized/invalid input and oversized output; never executes code or makes network requests.
- `text_justify_lines`: formats non-empty lines with left/right/center/full justification (`width` default 80 range 1..500; optional `skip_first`; accepts `<<<TEXT_JUSTIFY_LINES>>>`); preserves line endings, never truncates content, and rejects invalid or oversized input/output; never executes code or makes network requests.
- `text_margin_lines`: adds left/right ASCII space margins to each non-empty line (default left/right 0; optional skip_first); accepts text+options or `<<<TEXT_MARGIN_LINES>>>`; max 20_000 chars; never executes code or makes network requests.
- `mime_attachment_cid_map`: parses raw MIME and returns a JSON map of Content-ID tokens to attachment `filename`/`content_type` metadata (angle brackets stripped); never returns payloads or makes network requests.
- `mime_attachment_ctypes`: parses a raw MIME message via stdlib `email` and returns only a JSON list of decoded attachment `filename`/`name` parameters with declared `content_type` values (default `application/octet-stream`); rejects empty/oversized/malformed input; never returns payloads, executes code, writes attachments, or makes network requests.
- `mime_attachment_disposition`: parses a raw MIME message via stdlib `email` and returns only a JSON list of Content-Disposition `filename` and `disposition` values for attachment/inline parts; rejects empty/oversized/malformed input and never returns payloads, executes code, writes attachments, or makes network requests.
- `mime_attachment_encoding`: parses bounded raw MIME via stdlib `email` and returns only decoded filenames with normalized Content-Transfer-Encoding values (`7bit` when omitted); rejects malformed or oversized input/output and never decodes or returns payloads, executes code, writes attachments, or makes network requests.
- `mime_attachment_filenames_unique`: parses raw MIME and returns a JSON map of original attachment filenames to unique disambiguated names when duplicates exist (append -2/-3 before extension); never returns payloads or makes network requests.
- `text_pad_lines`: pads each non-empty line to a target width with leading/trailing ASCII spaces (`width` default 80 range 1..200; `side`: left/right/both default right; optional `skip_first`; accepts `<<<TEXT_PAD_LINES>>>`); rejects empty/oversized/invalid input; never executes code or makes network requests.
- `text_slug_lines`: slugifies each line independently with bounded Unicode-to-ASCII normalization (`separator` default `-`; `lowercase` and `skip_empty` default true; accepts `<<<TEXT_SLUG_LINES>>>`); preserves line endings and rejects invalid or oversized input/output; never executes code or makes network requests.
- `text_title_lines`: title-cases each line independently (`skip_empty` default true; `lowercase_first` default false; accepts `<<<TEXT_TITLE_LINES>>>`); preserves line endings and rejects invalid or oversized input/output; never executes code or makes network requests.
- `text_unique_lines`: deduplicates lines in first-seen order (optional `strip`, default true; accepts `<<<TEXT_UNIQUE_LINES>>>`); rejects empty/oversized/invalid input; never executes code or makes network requests.
