# Changelog

## Unreleased

### Added
- `morse`: International Morse encode/decode (`mode` encode|decode; `text` or `data`; max 20_000 chars); guide `MORSE_TOOL_GUIDE.md`.
- `rot13`: ROT13 self-inverse transform (`text` or `data`; max 20_000 chars); guide `ROT13_TOOL_GUIDE.md`.
- `base85`: Adobe ASCII85/Base85 encode/decode (`mode` encode|decode; `text` or `data`; max 20_000 chars); guide `BASE85_TOOL_GUIDE.md`.
- `punycode`: Punycode/IDNA encode/decode (`mode` encode|decode; `text` or `domain`; max 2000 chars); guide `PUNYCODE_TOOL_GUIDE.md`.
- `pluralize`: English pluralize/singularize (`mode` pluralize|singularize; `text` or `word`; common irregulars; max 2000 chars); guide `PLURALIZE_TOOL_GUIDE.md`.
- `csv_to_json`: header-required CSV → JSON array-of-objects (capped); no network. See `docs/guides/CSV_TO_JSON_TOOL_GUIDE.md`.
- `metaphone`: classic Metaphone phonetic code tool (max 2000 chars); no network. See `docs/guides/METAPHONE_TOOL_GUIDE.md`.
- `base58`: Bitcoin-alphabet Base58 encode/decode (`mode` encode|decode; `text` or `data`; max 20_000 chars); guide `BASE58_TOOL_GUIDE.md`.
- `JwtEncodeTool` (`jwt_encode`): HS256 JWT encode (stdlib hmac/hashlib/base64); companion to jwt_decode; no network. See `docs/guides/JWT_ENCODE_TOOL_GUIDE.md`.
- `crc32`: unsigned CRC32 hex digest of UTF-8 text (max 100_000 chars); guide `CRC32_TOOL_GUIDE.md`.
- `soundex`: American Soundex phonetic code for `text` (max 2000 chars); guide `SOUNDEX_TOOL_GUIDE.md`.
- `ini_parse`: parse INI/CFG into pretty JSON via stdlib configparser; guide `INI_PARSE_TOOL_GUIDE.md`.
- `url_normalize`: canonicalize URL scheme/host/ports/fragments; guide `URL_NORMALIZE_TOOL_GUIDE.md`.
- `levenshtein`: classic edit distance between `a`/`b` (max 2000 chars); guide `LEVENSHTEIN_TOOL_GUIDE.md`.
- `xml_escape`: escape/unescape XML special chars via `xml.sax.saxutils` (`mode` escape|unescape; max 20_000 chars); guide `XML_ESCAPE_TOOL_GUIDE.md`.
- `uuid_nil`: RFC 4122 nil UUID (or max when `mode=max`) for placeholder ids; guide `UUID_NIL_TOOL_GUIDE.md`.
- `base32_encode`: encode/decode via stdlib Base32 (`mode` encode|decode; max 20_000 chars); guide `BASE32_ENCODE_TOOL_GUIDE.md`.
- `jsonl_parse`: parse JSON Lines into a pretty JSON array (`mode` objects|any; max 500 lines / 20_000 chars); guide `JSONL_PARSE_TOOL_GUIDE.md`.
- `hmac_sign`: HMAC digest of text with a secret key (`sha256`/`sha1`/`sha512`; output hex|base64; never logs secret); guide `HMAC_SIGN_TOOL_GUIDE.md`.
- `cron_next`: next N UTC fire times for a 5-field cron expression (`count` default 5 max 20; optional `from_iso`; stdlib only); guide `CRON_NEXT_TOOL_GUIDE.md`.
- `semver_compare`: compare two SemVer versions (`-1`/`0`/`1` + human relation; sentinel `<<<SEMVER_COMPARE>>>`); guide `SEMVER_COMPARE_TOOL_GUIDE.md`.
- `csv_fillna`: fill empty CSV cells with a constant (`fill_value`, optional `columns`; sentinel `<<<CSV_FILLNA>>>`); guide `CSV_FILLNA_TOOL_GUIDE.md`.
- `ics_parse`: parse iCalendar VEVENT SUMMARY/DTSTART/DTEND/UID/LOCATION as JSON Lines (stdlib only; max 20_000 chars, 100 events); guide `ICS_PARSE_TOOL_GUIDE.md`.
- `html_links_extract`: extract HTML anchor href+text as JSON (`max_links` default 100); rejects script/style; guide `HTML_LINKS_EXTRACT_TOOL_GUIDE.md`.
- `markdown_toc`: nested Markdown TOC from ATX headings (`max_level` default 3); sentinel `<<<MARKDOWN_TOC>>>`; guide `MARKDOWN_TOC_TOOL_GUIDE.md`.
- `text_unique_lines`: order-preserving line dedupe (optional strip); sentinel `<<<TEXT_UNIQUE_LINES>>>`; guide `TEXT_UNIQUE_LINES_TOOL_GUIDE.md`.
- `mime_multipart_flatten`: recursively flatten nested multipart MIME to leaf metadata JSON without payloads; guide `MIME_MULTIPART_FLATTEN_TOOL_GUIDE.md`.
- `csv_transpose`: transpose CSV rows↔columns with padding; guide `CSV_TRANSPOSE_TOOL_GUIDE.md`.
- `text_collapse_blank`: collapse consecutive blank lines to a bounded `max_blank` (default 1); sentinel `<<<TEXT_COLLAPSE_BLANK>>>`; guide `TEXT_COLLAPSE_BLANK_TOOL_GUIDE.md`.
- Added the `mime_attachment_cid_map` safe tool for mapping MIME Content-ID tokens to attachment filename/content-type metadata without payloads (max 20_000 chars); guide + demo GIF.
- Added the `csv_window` safe tool for sliding CSV row windows with a preserved header (`window_size`/`step`/`start_row`/`index`; max 20_000 chars, 500 rows, 64 columns); guide + demo GIF.
- Added the `text_title_lines` safe tool for per-line title-casing with preserved line endings and optional lowercase-first handling (max 20_000 chars); guide + demo GIF.
- Added the `csv_stack` safe tool for vertically concatenating CSV documents with identical headers (`csvs` list or `<<<CSV_STACK>>>`; max 20_000 chars, 500 rows, 64 columns); guide + demo GIF.
- Added the `text_slug_lines` safe tool for per-line ASCII slugification with preserved line endings and configurable separator/casing/empty-line handling (max 20_000 chars); guide + demo GIF.
- Added the `text_justify_lines` safe tool for left/right/center/full line justification (default width 80, max 500, max 20_000 chars); guide + demo GIF.
- Added the `mime_attachment_encoding` safe tool for listing named MIME attachment Content-Transfer-Encoding values without decoding or returning payloads (max 20_000 chars); guide + demo GIF.
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
- `base58`: Bitcoin-alphabet Base58 encode/decode (`mode` encode|decode; `text` or `data`; max 20_000 chars); guide `BASE58_TOOL_GUIDE.md`.
- Added the `yaml_to_json` safe tool for converting a constrained YAML subset

- Added the `uuid4` safe tool for generating random version-4 UUID
  identifier(s) (optional `count` 1..16) for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 agent workflows. Opaque ids only — not cryptographic
  secrets.
- Added the `html_table` safe tool for extracting the first HTML table, or a
  selected 1-based table index, into markdown or CSV with bounded chars, rows,
  columns, and structured metadata for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 agent workflows.
