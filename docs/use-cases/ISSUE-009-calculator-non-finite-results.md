# Use Case: The calculator tool must return finite numbers only

**Issue:** #009
**Repository:** multi-bot-agentic

## Problem

`ISSUE-008` closed the gap where the `calculator` tool surfaced a `complex`
value as a successful result. A related gap remained: floating-point arithmetic
silently overflows to infinity in CPython, and `inf - inf` yields `nan`, without
raising an exception:

```python
1e300 * 1e300  # inf
1e300 * 1e300 - 1e300 * 1e300  # nan
```

The tool passed such values straight through `_format_value`, so the run
recorded a successful (`ok=True`) tool result whose content was `inf` or `nan`.
Downstream steps that expect a real numeric answer would then consume a
non-finite value as if it were valid.

## How this agent solves it

`_eval_node` now checks the result of every binary operation and raises
`CalculatorError("result is not a finite number")` when the value is a
non-finite float (`inf`/`-inf`/`nan`). The tool's existing error handling
converts that into a structured `ok=False` result with a clear message, so the
agent can recover or ask the model for a corrected expression instead of
propagating a non-finite value.

## Agentic design elements

| Component | Role |
|-----------|------|
| Tool adapter | Enforces the finite real-number contract it advertises |
| Decision engine | Sees a structured failure and can request a corrected action |
| Event log | Records the refusal reason instead of an opaque `inf`/`nan` value |

## Try it

```bash
pytest tests/test_calculator_tool.py::test_calculator_rejects_non_finite_result -q
```
