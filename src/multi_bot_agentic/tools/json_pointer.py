"""RFC 6901 JSON Pointer extraction tool.

Agent runs often need one stable value from a JSON payload using the IETF
JSON Pointer dialect (``/foo/0/bar``) rather than the project's simpler
``json_path`` dot/[index] dialect. This tool parses JSON with the standard
library and evaluates RFC 6901 pointers, including the empty pointer for the
whole document and ``~0``/``~1`` escapes. It never executes code, never
evaluates scripts/filters, and never makes a network request — matching the
``json_path``, ``json_format``, and ``json_query`` contracts for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:json_pointer:<payload>``, the JSON document and pointer may be supplied
either as separate ``text`` / ``pointer`` arguments (tests and programmatic
callers) or as a single ``text`` value split on the sentinel
``<<<JSON_POINTER>>>``.
"""

from __future__ import annotations

import json
import math
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_POINTER_CHARS: Final[int] = 512
_MAX_RESULT_CHARS: Final[int] = 20_000
_SPLIT_SENTINEL: Final[str] = "<<<JSON_POINTER>>>"


def _reject_non_finite(token: str) -> float:
    """Reject non-standard JSON constants accepted by Python's JSON decoder."""

    raise ValueError(f"{token} is not valid JSON")


def _parse_finite_float(token: str) -> float:
    """Parse a JSON float literal and reject non-finite overflow."""

    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"{token} overflows to a non-finite number and is not valid JSON")
    return value


class JsonPointerTool:
    """Extract one value from JSON using an RFC 6901 JSON Pointer."""

    name = "json_pointer"
    description = (
        "Extracts JSON values by RFC 6901 JSON Pointer (/foo/0/bar, empty for whole doc; "
        "text+pointer or <<<JSON_POINTER>>>); bounded, no exec."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Extract a JSON value for the requested pointer.

        Args:
            invocation: Tool invocation whose arguments hold ``text`` and
                optional ``pointer``, or ``text`` split on ``<<<JSON_POINTER>>>``.

        Returns:
            Tool result whose ``content`` is pretty JSON for the selected value,
            or ``ok=False`` with a structured failure for bad input, JSON,
            pointer, traversal, or result-size errors.
        """

        document, pointer, error = self._resolve_sides(invocation.arguments)
        if error is not None:
            return self._fail(error, {})

        assert document is not None and pointer is not None
        if not document.strip():
            return self._fail("document is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )
        if len(pointer) > _MAX_POINTER_CHARS:
            return self._fail(
                f"pointer exceeds max_chars={_MAX_POINTER_CHARS}",
                {"chars": len(pointer)},
            )

        try:
            parsed = json.loads(
                document,
                parse_constant=_reject_non_finite,
                parse_float=_parse_finite_float,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            return self._fail(f"invalid JSON: {exc}", {"chars": len(document)})

        tokens, pointer_error = self._parse_pointer(pointer)
        if pointer_error is not None:
            return self._fail(pointer_error, {"pointer": pointer})

        selected, traverse_error, traverse_metadata = self._traverse(parsed, tokens)
        if traverse_error is not None:
            return self._fail(traverse_error, {"pointer": pointer, **traverse_metadata})

        try:
            content = json.dumps(selected, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            return self._fail(f"result is not serializable JSON: {exc}", {"pointer": pointer})

        if len(content) > _MAX_RESULT_CHARS:
            return self._fail(
                f"result exceeds max_chars={_MAX_RESULT_CHARS}",
                {"pointer": pointer, "chars": len(content)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "pointer": pointer,
                "result_type": type(selected).__name__,
                "chars": len(content),
            },
        )

    @classmethod
    def _resolve_sides(cls, arguments: dict[str, object]) -> tuple[str | None, str | None, str | None]:
        """Resolve document/pointer from ``text``/``pointer`` or the split sentinel."""

        text = str(arguments.get("text", ""))
        if "pointer" in arguments:
            return text, str(arguments.get("pointer", "")), None

        if _SPLIT_SENTINEL not in text:
            return (
                None,
                None,
                (f"json_pointer requires text+pointer arguments, or a single text split on {_SPLIT_SENTINEL!r}"),
            )
        document, pointer = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in pointer:
            return None, None, "text contains more than one <<<JSON_POINTER>>> sentinel"
        return document.strip("\n"), pointer.strip("\n"), None

    @classmethod
    def _parse_pointer(cls, raw_pointer: str) -> tuple[list[str], str | None]:
        """Parse an RFC 6901 JSON Pointer into unescaped reference tokens.

        Args:
            raw_pointer: User-provided pointer text.

        Returns:
            Reference tokens and an optional failure message.
        """

        if raw_pointer == "":
            return [], None
        if not raw_pointer.startswith("/"):
            return [], "JSON Pointer must be empty or start with '/'"

        tokens: list[str] = []
        # Split on '/' but keep empty segments (e.g. // means empty key).
        for raw_token in raw_pointer.split("/")[1:]:
            if "~" in raw_token:
                # Reject incomplete escapes before applying the RFC unescape order.
                index = 0
                while index < len(raw_token):
                    if raw_token[index] != "~":
                        index += 1
                        continue
                    if index + 1 >= len(raw_token) or raw_token[index + 1] not in {"0", "1"}:
                        return [], f"invalid JSON Pointer escape in token: {raw_token!r}"
                    index += 2
                # RFC 6901: replace ~1 first, then ~0.
                raw_token = raw_token.replace("~1", "/").replace("~0", "~")
            tokens.append(raw_token)
        return tokens, None

    @staticmethod
    def _traverse(document: object, tokens: list[str]) -> tuple[object | None, str | None, dict[str, object]]:
        """Traverse a parsed JSON value with RFC 6901 reference tokens."""

        current = document
        for token in tokens:
            if isinstance(current, dict):
                if token not in current:
                    return None, f"key not found: {token}", {"segment": token}
                current = current[token]
                continue

            if isinstance(current, list):
                if token == "-":
                    return None, "array index '-' is not supported for extraction", {"segment": token}
                if not token.isdecimal() or (len(token) > 1 and token.startswith("0")):
                    return None, f"invalid array index: {token}", {"segment": token}
                index = int(token)
                if index >= len(current):
                    return None, f"index out of bounds: {index}", {"index": index, "length": len(current)}
                current = current[index]
                continue

            return None, f"cannot traverse into {type(current).__name__} with token {token!r}", {"segment": token}

        return current, None, {}

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
