# HitlEscalationCooldownGate Guide

![HitlEscalationCooldownGate demo](../../assets/demo/hitl-escalation-cooldown-gate.gif)

Cooldown after HITL deny/reject to block immediate re-escalation (advisory/hard; never network I/O)

Works with **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Gap vs AutoGen / CrewAI / LangGraph / Semantic Kernel

| Capability | multi-bot-agentic | Popular frameworks |
| --- | --- | --- |
| Focus | HitlEscalationCooldownGate | Often missing or proprietary |

## Usage

See unit tests under `tests/` for caller-driven examples. Never performs network I/O.
