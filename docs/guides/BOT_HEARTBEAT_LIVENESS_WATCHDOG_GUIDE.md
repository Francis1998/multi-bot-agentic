# BotHeartbeatLivenessWatchdog Guide

![BotHeartbeatLivenessWatchdog demo](../../assets/demo/bot-heartbeat-liveness-watchdog.gif)

Detect stale bots via per-bot heartbeats (alive/stale/unknown). Fills an AutoGen /
CrewAI / LangGraph liveness gap. Works with **GPT-6 Astra / Claude Opus 5.5 /
Gemini 4 Argon / Kimi K3.1 Pro**. Never performs network I/O.

Distinct from `SessionTtlExpirer` and `RunDeadlineWatchdog`.

## Usage

```python
from multi_bot_agentic.bot_heartbeat import BotHeartbeatLivenessWatchdog

dog = BotHeartbeatLivenessWatchdog(timeout_seconds=30.0)
dog.heartbeat("session-1", "researcher")
print(dog.status("session-1", "researcher").band)
```
