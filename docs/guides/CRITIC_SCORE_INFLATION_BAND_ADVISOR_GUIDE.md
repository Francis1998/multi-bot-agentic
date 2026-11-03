# CriticScoreInflationBandAdvisor Guide

![CriticScoreInflationBandAdvisor](../../assets/demo/critic-score-inflation.gif)

Offline helper.
Gap vs LangGraph/CrewAI/AutoGen critic score-inflation monitors. Distinct from `CriticCalibrationDriftBandAdvisor` / `CriticCollusionBandAdvisor`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.critic_score_inflation_band import CriticScoreInflationBandAdvisor

status = CriticScoreInflationBandAdvisor().advise("session-1", inflation_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
