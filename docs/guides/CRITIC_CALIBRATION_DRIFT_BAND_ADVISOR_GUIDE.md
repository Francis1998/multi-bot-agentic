# CriticCalibrationDriftBandAdvisor Guide

![CriticCalibrationDriftBandAdvisor](../../assets/demo/critic-calibration-drift.gif)

Offline HITL band guard for `drift_ratio`.
Gap vs LangGraph/CrewAI/AutoGen critic-calibration drift monitors. Distinct from `CriticCollusionBandAdvisor` / `CriticLatencySkewBandAdvisor`.

Works with **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.critic_calibration_drift_band import CriticCalibrationDriftBandAdvisor

status = CriticCalibrationDriftBandAdvisor().advise("session-1", drift_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
