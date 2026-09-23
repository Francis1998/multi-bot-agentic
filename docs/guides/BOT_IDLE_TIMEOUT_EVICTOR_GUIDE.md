        # BotIdleTimeoutEvictor Guide

        ![BotIdleTimeoutEvictor HITL flow](../../assets/demo/bot-idle-timeout-evictor.gif)

        Offline HITL control. Never performs network I/O.

        Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

        ## Usage

        ```python
from multi_bot_agentic.bot_idle_timeout import BotIdleTimeoutEvictor

report = BotIdleTimeoutEvictor().check("researcher", idle_seconds=280.0)
assert report.requires_human_review is True
print(report.band)
```


        ## Safety

        Always `requires_human_review=True`. Humans decide. See `SAFETY.md`.
