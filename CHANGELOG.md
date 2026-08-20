# Changelog

## Unreleased

### Added
- Added the `text_justify_lines` safe tool for left/right/center/full line justification (default width 80, max 500, max 20_000 chars); guide + demo GIF.
- Added the `json_patch_apply` safe tool for bounded RFC 6902 `add`/`remove`/`replace`/`move`/`copy`/`test` operations (max 20_000 chars, 200 operations); guide + demo GIF.
- Added the `text_margin_lines` safe tool for left/right ASCII margins on non-empty lines (max 20_000 chars); guide + demo GIF.
- Added the `json_diff_paths` safe tool for returning sorted dotted/bracket paths that differ between two JSON documents (max 20_000 chars per document, 2000 paths); guide + demo GIF.
- Added the `mime_attachment_disposition` safe tool for listing MIME Content-Disposition filenames and attachment/inline disposition types without returning payloads (max 20_000 chars); guide + demo GIF.
- Added the `text_pad_lines` safe tool for padding non-empty lines to a target width with ASCII spaces (default width 80, side right; max 20_000 chars); guide + demo GIF.
  equals/contains predicates; guide + demo GIF.
  (distinct from `json_path`); guide + demo GIF.
  identifier(s) (optional `count` 1..16) for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 agent workflows. Opaque ids only — not cryptographic
  secrets.
  selected 1-based table index, into markdown or CSV with bounded chars, rows,
  columns, and structured metadata for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 agent workflows.
  equals/contains predicates; guide + demo GIF.
  (distinct from `json_path`); guide + demo GIF.
  identifier(s) (optional `count` 1..16) for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 agent workflows. Opaque ids only — not cryptographic
  secrets.
  selected 1-based table index, into markdown or CSV with bounded chars, rows,
  columns, and structured metadata for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 agent workflows.
- Added the `json_flatten` safe tool for flattening nested JSON into dotted/bracket keys (max 20_000 chars input, 2000 keys); guide + demo GIF.
  equals/contains predicates; guide + demo GIF.
  (distinct from `json_path`); guide + demo GIF.
  identifier(s) (optional `count` 1..16) for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 agent workflows. Opaque ids only — not cryptographic
  secrets.
  selected 1-based table index, into markdown or CSV with bounded chars, rows,
  columns, and structured metadata for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 agent workflows.
- Added the `mime_attachment_sizes` safe tool for listing MIME attachment filenames with byte sizes without returning payloads (max 20_000 chars); guide + demo GIF.
- `text_outdent` safe tool: remove up to N leading spaces per non-empty line. See `docs/guides/TEXT_OUTDENT_TOOL_GUIDE.md`.
-  safe tool: unpivot wide CSV to long form (id_vars/value_vars). See .
- Added the `mime_attachment_names` safe tool for listing MIME attachment filenames without returning payloads (max 20_000 chars); guide + demo GIF.
- Added the `url_encode` safe tool for percent-encoding text via `urllib.parse.quote` (optional safe chars / plus-for-space; max 20_000 chars); guide + demo GIF.
- Added the `csv_unique` safe tool for deduplicating CSV rows by named column(s) (keep first; max 500 rows, 64 columns); guide + demo GIF.
- Added the `text_indent` safe tool for indenting non-empty lines by N spaces (default 2, max 32; optional skip_first; max 20_000 chars); guide + demo GIF.
- Added the `csv_sort` safe tool for sorting CSV rows by a named column (optional descending/numeric; max 500 rows, 64 columns); guide + demo GIF.
- Added the `text_squeeze_ws` safe tool for collapsing whitespace runs (optional preserve_newlines; max 20_000 chars); guide + demo GIF.
- Added the `hex_encode` safe tool for UTF-8 text → hex encoding (optional uppercase; max 20_000 chars); guide + demo GIF.
- Added the `csv_select_columns` safe tool for selecting/reordering CSV columns by name (max 500 rows, 64 columns); guide + demo GIF.
- Added the `text_case` safe tool for lower/upper/title/snake/kebab/camel conversion (max 20_000 chars); guide + demo GIF.
- Added the `jwt_decode` safe tool for base64url-decoding JWT header+payload claims without signature verification (never trust output); guide + demo GIF.
- Added the `csv_filter` safe tool for filtering CSV rows by named-column
  equals/contains predicates; guide + demo GIF.
- Added the `json_pointer` safe tool for RFC 6901 JSON Pointer extraction
  (distinct from `json_path`); guide + demo GIF.


## Unreleased

### Added
- Added the `yaml_to_json` safe tool for converting a constrained YAML subset

- Added the `uuid4` safe tool for generating random version-4 UUID
  identifier(s) (optional `count` 1..16) for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 agent workflows. Opaque ids only — not cryptographic
  secrets.
- Added the `html_table` safe tool for extracting the first HTML table, or a
  selected 1-based table index, into markdown or CSV with bounded chars, rows,
  columns, and structured metadata for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 agent workflows.
