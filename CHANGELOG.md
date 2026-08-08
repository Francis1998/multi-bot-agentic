# Changelog

## Unreleased

### Added

- Added the `uuid4` safe tool for generating random version-4 UUID
  identifier(s) (optional `count` 1..16) for GPT-5.5 / Claude Sonnet 4.6 /
  Gemini 3.x / Kimi K2 agent workflows. Opaque ids only — not cryptographic
  secrets.
- Added the `html_table` safe tool for extracting the first HTML table, or a
  selected 1-based table index, into markdown or CSV with bounded chars, rows,
  columns, and structured metadata for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
  Kimi K2 agent workflows.
