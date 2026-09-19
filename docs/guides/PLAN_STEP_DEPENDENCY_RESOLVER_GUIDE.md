# PlanStepDependencyResolver Guide

![PlanStepDependencyResolver demo](../../assets/demo/plan-step-dependency-resolver.gif)

Topological plan-step ordering with cycle/missing-dep detection (never network I/O).

Works with **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Gap vs AutoGen / CrewAI / LangGraph / Semantic Kernel

| Capability | multi-bot-agentic | Popular frameworks |
| --- | --- | --- |
| Focus | PlanStepDependencyResolver | Often buried in graph runtimes |

## Usage

See unit tests under `tests/` for caller-driven examples. Never performs network I/O.
