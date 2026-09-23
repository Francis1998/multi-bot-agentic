        # DebateRoundLimiter Guide

        ![DebateRoundLimiter HITL flow](../../assets/demo/debate-round-limiter.gif)

        Offline HITL control. Never performs network I/O.

        Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

        ## Usage

        ```python
from multi_bot_agentic.debate_round_limiter import DebateRoundLimiter

status = DebateRoundLimiter().check("sess-1", rounds_used=4, max_rounds=5)
assert status.requires_human_review is True
print(status.band, status.remaining)
```


        ## Safety

        Always `requires_human_review=True`. Humans decide. See `SAFETY.md`.
