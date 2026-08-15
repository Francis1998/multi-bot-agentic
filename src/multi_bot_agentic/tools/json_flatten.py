"""Deterministic JSON flattening tool.

Agents often need nested JSON observations reduced to a flat key/value map before
the next model turn. Asking a model to flatten structures is brittle (invented
keys, dropped array indexes, inconsistent separators). This tool parses JSON
with the standard library and emits dotted/bracket keys such as ``a.b[0].c`` with
a configurable separator for object nesting. It never executes code or makes
network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
workers.
"""

from __future__ import annotations

import json
import math
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_KEYS: Final[int] = 2000
_DEFAULT_SEPARATOR: Final[str] = "."


def _reject_non_finite(token: str) -> float:
    """Reject non-standard JSON constants accepted by Python's JSON decoder."""

    raise ValueError(f"{token} is not valid JSON")


def _parse_finite_float(token: str) -> float:
    """Parse a JSON float literal and reject values that overflow to infinity."""

    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"{token} overflows to a non-finite number and is not valid JSON")
    return value


class JsonFlattenTool:
    """Flatten nested JSON objects and arrays into dotted/bracket keys."""

    name = "json_flatten"
    description = (
        "Flattens nested JSON into dotted/bracket keys (separator default .); max 20_000 chars input and 2000 keys."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Flatten a JSON document into a flat key/value map."""

        document = str(invocation.arguments.get("text", ""))
        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        separator = str(invocation.arguments.get("separator", _DEFAULT_SEPARATOR))
        if not separator:
            return self._fail("separator must be non-empty", {"separator": separator})
        if len(separator) > 16:
            return self._fail("separator exceeds max length 16", {"separator": separator})

        try:
            parsed = json.loads(
                document,
                parse_constant=_reject_non_finite,
                parse_float=_parse_finite_float,
            )
        except json.JSONDecodeError as exc:
            return self._fail(f"invalid JSON: {exc.msg}", {"position": exc.pos})
        except ValueError as exc:
            return self._fail(f"invalid JSON: {exc}", {})

        flattened: dict[str, object] = {}
        try:
            _flatten_value(parsed, "", separator, flattened)
        except _FlattenLimitError as exc:
            return self._fail(str(exc), {"keys": len(flattened)})

        content = json.dumps(flattened, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if len(content) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"flatten output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(content), "keys": len(flattened)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "keys": len(flattened),
                "separator": separator,
                "chars": len(content),
                "input_chars": len(document),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


class _FlattenLimitError(RuntimeError):
    """Raised when flattening exceeds the configured key cap."""


def _flatten_value(
    value: object,
    prefix: str,
    separator: str,
    output: dict[str, object],
) -> None:
    """Recursively flatten one JSON value into the output map."""

    if isinstance(value, dict):
        if not value and prefix:
            _store_key(prefix, value, output)
            return
        for key, nested in value.items():
            key_text = str(key)
            next_prefix = f"{prefix}{separator}{key_text}" if prefix else key_text
            _flatten_value(nested, next_prefix, separator, output)
        return

    if isinstance(value, list):
        if not value and prefix:
            _store_key(prefix, value, output)
            return
        for index, nested in enumerate(value):
            next_prefix = f"{prefix}[{index}]"
            _flatten_value(nested, next_prefix, separator, output)
        return

    if prefix:
        _store_key(prefix, value, output)


def _store_key(key: str, value: object, output: dict[str, object]) -> None:
    """Store one flattened key, enforcing the key cap."""

    if len(output) >= _MAX_KEYS:
        raise _FlattenLimitError(f"flatten exceeds max_keys={_MAX_KEYS}")
    output[key] = value
