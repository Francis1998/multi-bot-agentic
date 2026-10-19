# MemoryNamespaceLeakAdvisor Guide

![MemoryNamespaceLeakAdvisor](../../assets/demo/memory-namespace-leak.gif)

Offline HITL advisor for `leak_ratio` bands.
Gap vs LangGraph/CrewAI/AutoGen memory-namespace leak monitors. Distinct from `BlackboardLeaseThrashAdvisor` / `WorkerStarvationBandAdvisor`.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.memory_namespace_leak import MemoryNamespaceLeakAdvisor

status = MemoryNamespaceLeakAdvisor().advise("s1", leak_ratio=0.3)
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
