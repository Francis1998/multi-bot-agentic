# crc32 Tool Guide

![crc32 demo](../../assets/demo/crc32.gif)

Compute deterministic CRC32 checksums for content-integrity checks before the
next GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

Agent pipelines need a stable CRC32 fingerprint when comparing handoff blobs
or cache keys. Models invent digests; `crc32` uses stdlib `zlib` with no
network access (inspired by content-integrity tooling in agent pipelines).

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="crc32",
        arguments={"text": "hello"},
    )
)
```

## Bounds & Safety

- Required: `text` (max 100_000 chars)
- Content is the unsigned hexadecimal CRC32 digest; metadata includes `crc32`
- Never executes code or makes network requests
