# PlanStepDependencyResolver Guide

![PlanStepDependencyResolver demo](../../assets/demo/plan-step-dependency-resolver.gif)

Topological plan-step ordering with cycle/missing-dep detection (never network I/O).

Works with **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Gap vs AutoGen / CrewAI / LangGraph / Semantic Kernel

| Capability | multi-bot-agentic | Popular frameworks |
| --- | --- | --- |
| Focus | PlanStepDependencyResolver | Often buried in graph runtimes |

## Usage

See unit tests under `tests/` for caller-driven examples. Never performs network I/O.
