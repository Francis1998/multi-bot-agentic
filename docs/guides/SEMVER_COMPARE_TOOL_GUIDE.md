# semver_compare Tool Guide

![semver_compare demo](../../assets/demo/semver-compare.gif)

Compare two semantic versions before the next GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 turn.

## Why

Version gating is ubiquitous in DevOps agent toolkits, but this repo had no
SemVer helper. Models routinely mis-order pre-releases such as `1.0.0-alpha`
vs `1.0.0`. `semver_compare` applies SemVer 2.0.0 precedence deterministically.

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="semver_compare",
        arguments={"version_a": "1.0.0-alpha", "version_b": "1.0.0"},
    )
)
```

Sentinel form: `1.2.3<<<SEMVER_COMPARE>>>1.2.4`

Content is `-1`, `0`, or `1` on the first line, then a human relation such as
`1.0.0-alpha < 1.0.0`.

## Bounds & Safety

- Each version max 128 chars
- Core `major.minor.patch` required; optional pre-release and build metadata
- Build metadata is ignored for comparison
- Never executes code or makes network requests
