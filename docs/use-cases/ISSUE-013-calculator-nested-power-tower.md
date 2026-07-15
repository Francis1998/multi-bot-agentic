# Use Case: The calculator tool must bound nested power towers

**Issue:** #013
**Repository:** multi-bot-agentic

## Problem

The `calculator` tool bounds a single exponent (`_MAX_EXPONENT`) so a hostile
expression such as `9 ** 9999` is refused before it is evaluated. That guard
inspects only *one* `**` operator's exponent, so it does not stop a *nested*
power tower where every individual exponent stays within the bound:

```python
(10**60)**60          # 10**3600 — a 3601-digit integer, accepted (ok=True)
((10**60)**60)**60     # 10**216000 — grows tower-exponentially
```

Each exponent (`60`) is well within `_MAX_EXPONENT`, so the per-operation bound
never fires while the integer result grows tower-exponentially. Evaluating such
an expression exhausts CPU and memory, and — once the result exceeds CPython's
integer-to-string conversion limit (4300 digits) — `_format_value` raised an
**uncaught** `ValueError`, crashing the tool instead of returning a structured
failure. The tool's own docstring promised that "a hostile expression such as
`9**9**9` cannot exhaust CPU or memory", so this was a real gap in that
guarantee.

## How this agent solves it

`_eval_node` now enforces a *result-magnitude* bound in addition to the exponent
bound:

- Before an integer `base ** exp` is computed, the result size is estimated from
  the operands (`exp * base.bit_length()`) and refused if it would exceed
  `_MAX_RESULT_BITS` (~4096 bits, ~1233 digits). The oversized integer is never
  materialised.
- After any binary operation, an integer result whose `bit_length()` exceeds the
  bound is refused as well, catching multiplication chains and any residual.

Both paths raise `CalculatorError("result exceeds safe magnitude of 4096
bits")`, which the tool converts into a structured `ok=False` result. Ordinary
bounded powers (`2 ** 64`, `10 ** 64`) remain evaluable.

## Agentic design elements

| Component | Role |
|-----------|------|
| Tool adapter | Enforces the compute/memory bound it advertises, for towers too |
| Decision engine | Sees a structured failure and can request a corrected action |
| Event log | Records the refusal reason instead of crashing the run |

## Try it

```bash
pytest tests/test_calculator_tool.py::test_calculator_bounds_nested_power_tower -q
```
