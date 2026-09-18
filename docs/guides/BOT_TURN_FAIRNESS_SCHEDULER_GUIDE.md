# BotTurnFairnessScheduler Guide

![BotTurnFairnessScheduler demo](../../assets/demo/bot-turn-fairness-scheduler.gif)

Per-session least-served bot turn fairness with advisory/hard skew cap (never network I/O)

Works with **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Gap vs AutoGen / CrewAI / LangGraph / Semantic Kernel

| Capability | multi-bot-agentic | Popular frameworks |
| --- | --- | --- |
| Focus | BotTurnFairnessScheduler | Often missing or proprietary |

## Usage

See unit tests under `tests/` for caller-driven examples. Never performs network I/O.
