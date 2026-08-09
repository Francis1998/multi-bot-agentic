# Changelog

## Unreleased

### Added
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
