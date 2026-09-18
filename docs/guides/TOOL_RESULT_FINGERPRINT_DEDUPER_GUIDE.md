# ToolResultFingerprintDeduper Guide

![ToolResultFingerprintDeduper demo](../../assets/demo/tool-result-fingerprint-deduper.gif)

Fingerprint-hash tool-result dedupe per session to avoid re-injecting identical observations (never network I/O)

Works with **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Gap vs AutoGen / CrewAI / LangGraph / Semantic Kernel

| Capability | multi-bot-agentic | Popular frameworks |
| --- | --- | --- |
| Focus | ToolResultFingerprintDeduper | Often missing or proprietary |

## Usage

See unit tests under `tests/` for caller-driven examples. Never performs network I/O.
