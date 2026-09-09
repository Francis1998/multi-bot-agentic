# Budgeted Step Planner Guide

![Budgeted step planner demo](../../assets/demo/budgeted-step-planner.gif)

Token/cost-aware step caps before LLM calls. Clamps `max_steps` by
`max_tokens // estimated_tokens_per_step` so agent loops cannot burn budget
unbounded.

Works with **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2** runs.

## Gap vs LangGraph

| Capability | multi-bot-agentic | LangGraph |
| --- | --- | --- |
| Focus | Preflight step/token clamp | Graph loops often unbounded |
| Wiring | Caller-driven `plan`/`reserve` | Node/edge recursion |
| Failure | Explicit `BudgetPlan.reason` | Runtime recursion limits |

## Usage

```python
from multi_bot_agentic.budget_planner import BudgetedStepPlanner

planner = BudgetedStepPlanner()
plan = planner.plan(max_steps=10, max_tokens=4000, estimated_tokens_per_step=800)
assert plan.allowed_steps == 5
# after each GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 step:
planner.reserve(750)
print(planner.remaining_tokens, planner.remaining_steps)
```
