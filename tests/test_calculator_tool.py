"""Tests for the sandboxed calculator tool."""

from __future__ import annotations

import pytest

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.calculator import CalculatorTool


def _run(expression: str) -> tuple[bool, str]:
    """Execute the calculator tool for an expression.

    Args:
        expression: Arithmetic expression to evaluate.

    Returns:
        Tuple of ``(ok, content)`` from the tool result.
    """

    result = CalculatorTool().execute(ToolInvocation(tool_name="calculator", arguments={"text": expression}))
    return result.ok, result.content


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 + 3 * 4", "14"),
        ("(2 + 3) * 4", "20"),
        ("10 / 4", "2.5"),
        ("10 // 4", "2"),
        ("2 ** 8", "256"),
        ("-7 + 2", "-5"),
        ("7 % 3", "1"),
    ],
)
def test_calculator_evaluates_valid_expressions(expression: str, expected: str) -> None:
    """Valid arithmetic expressions yield the exact numeric result."""

    ok, content = _run(expression)

    assert ok is True
    assert content == expected


def test_calculator_rejects_empty_expression() -> None:
    """An empty expression returns a structured failure, not a crash."""

    ok, content = _run("   ")

    assert ok is False
    assert "empty" in content


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('echo hi')",
        "open('secret.txt')",
        "value + 1",
        "1 if True else 2",
        "[1, 2, 3]",
    ],
)
def test_calculator_rejects_non_arithmetic_syntax(expression: str) -> None:
    """Names, calls, and non-arithmetic syntax are refused via the AST allowlist."""

    ok, _content = _run(expression)

    assert ok is False


def test_calculator_bounds_exponent_to_prevent_dos() -> None:
    """A huge exponent is rejected rather than evaluated, bounding compute."""

    ok, content = _run("9 ** 9999")

    assert ok is False
    assert "exponent" in content


def test_calculator_reports_division_by_zero() -> None:
    """Division by zero is reported as a failure, not raised."""

    ok, content = _run("1 / 0")

    assert ok is False
    assert "could not evaluate" in content
