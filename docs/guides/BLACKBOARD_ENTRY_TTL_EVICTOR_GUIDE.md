# BlackboardEntryTtlEvictor Guide

![BlackboardEntryTtlEvictor demo](../../assets/demo/blackboard-entry-ttl-evictor.gif)

Per-key TTL tracking and eviction for shared blackboard entries (never network I/O).

Works with **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Gap vs AutoGen / CrewAI / LangGraph / Semantic Kernel

| Capability | multi-bot-agentic | Popular frameworks |
| --- | --- | --- |
| Focus | BlackboardEntryTtlEvictor | Often missing per-entry TTL |

## Usage

See unit tests under `tests/` for caller-driven examples. Never performs network I/O.
