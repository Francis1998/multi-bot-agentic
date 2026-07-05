"""Sandboxed arithmetic calculator tool.

Agents frequently need exact arithmetic that a language model cannot be trusted
to compute reliably. This tool evaluates a numeric expression without ever
calling :func:`eval`: it parses the expression into an AST and walks an
allowlist of numeric node/operator types. Names, attribute access, function
calls, and comprehensions are rejected, and exponents are bounded so a hostile
expression such as ``9**9**9`` cannot exhaust CPU or memory.
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_EXPRESSION_CHARS: Final[int] = 200
_MAX_EXPONENT: Final[int] = 64

_BINARY_OPERATORS: Final[dict[type[ast.operator], Callable[[float, float], float]]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS: Final[dict[type[ast.unaryop], Callable[[float], float]]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class CalculatorError(ValueError):
    """Raised when an expression is unsafe, malformed, or unsupported."""


class CalculatorTool:
    """Evaluate arithmetic expressions safely via an AST allowlist."""

    name = "calculator"
    description = "Evaluates an arithmetic expression without eval (sandboxed AST)."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Evaluate the expression supplied in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                arithmetic expression.

        Returns:
            Tool result with the computed value, or ``ok=False`` and an
            explanation when the expression is empty, too long, or invalid.
        """

        expression = str(invocation.arguments.get("text", "")).strip()
        if not expression:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="expression is empty",
                metadata={},
            )
        if len(expression) > _MAX_EXPRESSION_CHARS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"expression exceeds max_chars={_MAX_EXPRESSION_CHARS}",
                metadata={"chars": len(expression)},
            )

        try:
            tree = ast.parse(expression, mode="eval")
            value = self._eval_node(tree.body)
        except CalculatorError as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=str(error),
                metadata={"expression": expression},
            )
        except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError) as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"could not evaluate expression: {error}",
                metadata={"expression": expression},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=self._format_value(value),
            metadata={"expression": expression},
        )

    @classmethod
    def _eval_node(cls, node: ast.AST) -> float:
        """Recursively evaluate an allowlisted arithmetic AST node.

        Args:
            node: AST node to evaluate.

        Returns:
            Numeric value of the node.

        Raises:
            CalculatorError: If the node uses disallowed syntax.
        """

        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise CalculatorError("only integer and float literals are allowed")
            return node.value
        if isinstance(node, ast.BinOp):
            operator_type = type(node.op)
            binary_operator = _BINARY_OPERATORS.get(operator_type)
            if binary_operator is None:
                raise CalculatorError(f"operator not allowed: {operator_type.__name__}")
            left = cls._eval_node(node.left)
            right = cls._eval_node(node.right)
            if operator_type is ast.Pow and abs(right) > _MAX_EXPONENT:
                raise CalculatorError(f"exponent exceeds safe bound {_MAX_EXPONENT}")
            return binary_operator(left, right)
        if isinstance(node, ast.UnaryOp):
            unary_type = type(node.op)
            unary_operator = _UNARY_OPERATORS.get(unary_type)
            if unary_operator is None:
                raise CalculatorError(f"unary operator not allowed: {unary_type.__name__}")
            return unary_operator(cls._eval_node(node.operand))
        raise CalculatorError(f"unsupported syntax: {type(node).__name__}")

    @staticmethod
    def _format_value(value: float) -> str:
        """Render a numeric result without a spurious trailing ``.0``.

        Args:
            value: Computed numeric value.

        Returns:
            Compact string representation.
        """

        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
