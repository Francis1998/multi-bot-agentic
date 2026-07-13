"""JSON validation and canonicalization tool.

Agent runs frequently pass JSON between steps (tool outputs, API payloads,
model-emitted structures). A malformed or inconsistently ordered document is a
common source of downstream failures. This tool validates a JSON document and
re-serialises it into a canonical, human-readable form (2-space indent, sorted
keys) without ever executing code. Invalid input returns a structured failure
with the parser's message rather than raising, matching the calculator tool's
contract.
"""

from __future__ import annotations

import json
import math
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000


def _reject_non_finite(token: str) -> float:
    """Reject the non-standard ``NaN``/``Infinity``/``-Infinity`` JSON tokens.

    Python's :func:`json.loads` accepts these three constants by default, but
    RFC 8259 does not permit them and strict parsers (for example JavaScript's
    ``JSON.parse``) reject them. Passing this handler as ``parse_constant`` makes
    the validator reject such documents rather than round-tripping them into
    output that is not valid JSON.

    Args:
        token: The literal constant token encountered by the parser.

    Raises:
        ValueError: Always, identifying the offending token.
    """

    raise ValueError(f"{token} is not valid JSON")


def _parse_finite_float(token: str) -> float:
    """Parse a JSON float token, rejecting values that overflow to infinity.

    A finite numeric literal whose magnitude exceeds the IEEE-754 double range
    (for example ``1e400``) is parsed by Python's default ``float`` into
    ``inf``. Unlike the bare ``Infinity`` token, this bypasses ``parse_constant``
    entirely, so such a document was accepted and then re-serialised as the
    non-standard ``Infinity`` literal — output that is not valid JSON. Routing
    floats through this handler rejects the document at validation instead.

    Args:
        token: The numeric float token encountered by the parser.

    Returns:
        The parsed float when finite.

    Raises:
        ValueError: When the literal is not a finite double.
    """

    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"{token} overflows to a non-finite number and is not valid JSON")
    return value


class JsonFormatTool:
    """Validate and canonicalize a JSON document."""

    name = "json_format"
    description = "Validates a JSON document and returns it canonicalized (sorted keys, indented)."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Validate and canonicalize the JSON document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the JSON
                document to validate.

        Returns:
            Tool result with the canonicalized document, or ``ok=False`` and an
            explanation when the document is empty, too long, or invalid JSON.
        """

        document = str(invocation.arguments.get("text", "")).strip()
        if not document:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="document is empty",
                metadata={},
            )
        if len(document) > _MAX_DOCUMENT_CHARS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                metadata={"chars": len(document)},
            )

        try:
            parsed = json.loads(
                document,
                parse_constant=_reject_non_finite,
                parse_float=_parse_finite_float,
            )
        except (json.JSONDecodeError, ValueError) as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"invalid JSON: {error}",
                metadata={"chars": len(document)},
            )

        canonical = json.dumps(parsed, indent=2, sort_keys=True, ensure_ascii=False)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=canonical,
            metadata={"top_level_type": type(parsed).__name__},
        )
