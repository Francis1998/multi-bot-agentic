# Use Case: PII redaction must not mangle non-address dotted numbers

**Issue:** #012
**Repository:** multi-bot-agentic

## Problem

The `redact` tool scrubs common PII (emails, phone numbers, SSNs, IPv4
addresses) before free-form text is persisted to the durable event log. Its
IPv4 pattern matched any four dot-separated groups of one to three digits:

```python
re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
```

`\d{1,3}` accepts any value from `0` to `999`, but a real IPv4 octet only ranges
`0-255`. Any dotted-quad-shaped number was therefore replaced with `[IP]`, even
when it can never be an address. A build/version string was silently corrupted:

```text
input:  "build 300.400.500.600 shipped"
output: "build [IP] shipped"   # non-PII value destroyed
```

This is a data-quality defect: the tool mangled unrelated data (and hid the real
value from anyone reading the scrubbed, replayable event log) without any
privacy benefit, because the value was never an IP address.

## How this agent solves it

Each octet is now bounded to `0-255` so genuine addresses are still redacted
while non-address dotted numbers are preserved:

```python
re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
)
```

```text
input:  "build 300.400.500.600 shipped"      -> unchanged
input:  "host 192.168.1.1 and 10.0.0.255"     -> "host [IP] and [IP]"
```

## Agentic design elements

| Component | Role |
|-----------|------|
| Safety controls | Redaction sanitises real PII before it reaches durable storage |
| Event log | Retains legitimate non-PII data instead of an opaque `[IP]` |
| Tool adapter | Returns per-category counts so redaction is auditable |

## Try it

```bash
pytest tests/test_redaction_tool.py::test_redact_ignores_dotted_numbers_with_out_of_range_octets -q
```
