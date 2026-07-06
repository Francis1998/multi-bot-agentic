# Use Case: The calculator tool must return real numbers only

**Issue:** #008
**Repository:** multi-bot-agentic

## Problem

The `calculator` tool advertises real arithmetic and annotates a `float` result.
Python, however, evaluates a fractional power of a negative base to a `complex`
value:

```python
(-8) ** 0.5  # (1.7319121124709868e-16+2.8284271247461903j)
```

The tool passed such a value straight through `_format_value`, which only
special-cases `float`, so the run recorded a successful (`ok=True`) tool result
whose content was an opaque `(...j)` string. Downstream steps that expect a
numeric answer would then consume a value that is neither a valid number nor a
clear error.

## How this agent solves it

`_eval_node` now checks the result of every binary operation and raises
`CalculatorError("result is not a real number")` when the value is `complex`.
The tool's existing error handling converts that into a structured
`ok=False` result with a clear message, so the agent can recover or ask the
model for a corrected expression instead of propagating a complex value.

## Agentic design elements

| Component | Role |
|-----------|------|
| Tool adapter | Enforces the real-number contract it advertises |
| Decision engine | Sees a structured failure and can request a corrected action |
| Event log | Records the refusal reason instead of an opaque complex value |

## Try it

```bash
pytest tests/test_calculator_tool.py::test_calculator_rejects_complex_result -q
```
