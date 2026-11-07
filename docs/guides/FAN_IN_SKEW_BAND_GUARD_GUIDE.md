# FanInSkewBandGuard Guide

![FanInSkewBandGuard](../../assets/demo/fan-in-skew-band-guard.gif)

Closes AutoGen / CrewAI / LangGraph fan-in latency skew gaps.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `FanInBarrierGate` and `ToolCallWaveScheduler`.

## Usage

```python
from multi_bot_agentic.fan_in_skew_band import FanInSkewBandGuard

status = FanInSkewBandGuard().check("session-1", fastest_s=1.0, slowest_s=2.0)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
