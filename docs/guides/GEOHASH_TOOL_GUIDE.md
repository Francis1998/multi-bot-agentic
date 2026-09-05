# Geohash Tool Guide

![Geohash demo](../../assets/demo/geohash.gif)

Deterministic lat/lon ↔ geohash codec for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Why

Models invent ad-hoc location codes. This tool encodes coordinates to geohash or decodes a geohash to a lat/lon center with no network. Inspired by location helpers in popular agent/tool runtimes (CrewAI/LangChain community utilities).

## Usage

```python
from multi_bot_agentic.tools.geohash import GeohashTool
from multi_bot_agentic.models import ToolInvocation

tool = GeohashTool()
encoded = tool.execute(ToolInvocation(
    tool_name="geohash",
    arguments={"lat": 37.7749, "lon": -122.4194, "precision": 7},
))
assert encoded.content == "9q8yyk8"
```

## Bounds

- Precision: 1..12 (default 7)
- Modes: `encode` (default), `decode`
- Encode args: `lat`/`lon` or `latitude`/`longitude`
- Decode args: `geohash` / `text` / `hash`

## Safety

Allowlisted; no network; pure local bit-interleaving over the geohash base32 alphabet.
