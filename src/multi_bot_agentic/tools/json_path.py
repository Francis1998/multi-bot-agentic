"""Deterministic JSON path extraction tool.

Agent runs often need one stable value from a JSON payload: a nested id, the
first item name, or the whole canonical document. Asking a model to extract that
value is brittle (missed array bounds, invented keys, inconsistent formatting).
This tool parses JSON with the standard library and evaluates a deliberately
small path dialect: dot-separated object keys plus ``[index]`` array lookups. It
never executes code, never evaluates scripts/filters, and never makes a network
request, matching the ``json_format``, ``regex``, and ``html_strip`` contracts.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:json_path:<payload>``, the JSON document and path may be supplied either
as separate ``text`` / ``path`` arguments (tests and programmatic callers) or as
a single ``text`` value split on the sentinel ``<<<JSON_PATH>>>``.
"""

from __future__ import annotations

import json
import math
import re
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_PATH_CHARS: Final[int] = 256
_MAX_RESULT_CHARS: Final[int] = 20_000
_SPLIT_SENTINEL: Final[str] = "<<<JSON_PATH>>>"
_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*\Z")
_UNSUPPORTED_PATH_MARKERS: Final[tuple[str, ...]] = ("..", "?", "|", "*", "(", ")", "{", "}", ";")

_PathToken = str | int


def _reject_non_finite(token: str) -> float:
    """Reject non-standard JSON constants accepted by Python's JSON decoder.

    Args:
        token: Constant token from the JSON document.

    Raises:
        ValueError: Always, identifying the offending token.
    """

    raise ValueError(f"{token} is not valid JSON")


def _parse_finite_float(token: str) -> float:
    """Parse a JSON float literal and reject values that overflow to infinity.

    Args:
        token: Float token from the JSON document.

    Returns:
        Parsed finite float.

    Raises:
        ValueError: When the literal overflows to a non-finite value.
    """

    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"{token} overflows to a non-finite number and is not valid JSON")
    return value


class JsonPathTool:
    """Extract one value from JSON using a small deterministic path dialect."""

    name = "json_path"
    description = "Extracts JSON values by simple dot/[index] path (text+path or <<<JSON_PATH>>>); bounded, no exec."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Extract a JSON value for the requested path.

        Args:
            invocation: Tool invocation whose arguments hold ``text`` and
                optional ``path``, or ``text`` split on ``<<<JSON_PATH>>>``.

        Returns:
            Tool result whose ``content`` is pretty JSON for the selected value,
            or ``ok=False`` with a structured failure for bad input, JSON, path,
            traversal, or result-size errors.
        """

        document, path, error = self._resolve_sides(invocation.arguments)
        if error is not None:
            return self._fail(error, {})

        assert document is not None and path is not None
        if not document.strip():
            return self._fail("document is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )
        if len(path) > _MAX_PATH_CHARS:
            return self._fail(
                f"path exceeds max_chars={_MAX_PATH_CHARS}",
                {"chars": len(path)},
            )

        try:
            parsed = json.loads(
                document,
                parse_constant=_reject_non_finite,
                parse_float=_parse_finite_float,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            return self._fail(f"invalid JSON: {exc}", {"chars": len(document)})

        tokens, path_error = self._parse_path(path)
        if path_error is not None:
            return self._fail(path_error, {"path": path})

        selected, traverse_error, traverse_metadata = self._traverse(parsed, tokens)
        if traverse_error is not None:
            return self._fail(traverse_error, {"path": path, **traverse_metadata})

        try:
            content = json.dumps(selected, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            return self._fail(f"result is not serializable JSON: {exc}", {"path": path})

        if len(content) > _MAX_RESULT_CHARS:
            return self._fail(
                f"result exceeds max_chars={_MAX_RESULT_CHARS}",
                {"path": path, "chars": len(content)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "path": path,
                "result_type": type(selected).__name__,
                "chars": len(content),
            },
        )

    @classmethod
    def _resolve_sides(cls, arguments: dict[str, object]) -> tuple[str | None, str | None, str | None]:
        """Resolve document/path from ``text``/``path`` or the split sentinel.

        Args:
            arguments: Tool invocation arguments.

        Returns:
            ``(document, path, error)`` — exactly one of the sides-pair or the
            error string is populated.
        """

        text = str(arguments.get("text", ""))
        if "path" in arguments:
            return text, str(arguments.get("path", "")), None

        if _SPLIT_SENTINEL not in text:
            return (
                None,
                None,
                (f"json_path requires text+path arguments, or a single text split on {_SPLIT_SENTINEL!r}"),
            )
        document, path = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in path:
            return None, None, "text contains more than one <<<JSON_PATH>>> sentinel"
        return document.strip("\n"), path.strip("\n").strip(), None

    @classmethod
    def _parse_path(cls, raw_path: str) -> tuple[list[_PathToken], str | None]:
        """Parse the supported dot/[index] path dialect into tokens.

        Args:
            raw_path: User-provided path text.

        Returns:
            Path tokens and an optional failure message.
        """

        path = raw_path.strip()
        if path in {"", "$"}:
            return [], None
        if path.startswith("$"):
            return [], "path may only use '$' by itself for the whole document"
        for marker in _UNSUPPORTED_PATH_MARKERS:
            if marker in path:
                return [], f"unsupported JSON path syntax: {marker}"

        if path.startswith("."):
            path = path[1:]
            if not path:
                return [], "path has an empty segment"

        tokens: list[_PathToken] = []
        index = 0
        while index < len(path):
            character = path[index]
            if character == ".":
                return [], "path has an empty segment"
            if character == "[":
                close_index = path.find("]", index + 1)
                if close_index == -1:
                    return [], "array index is missing closing ']'"
                raw_index = path[index + 1 : close_index]
                if not raw_index.isdecimal():
                    return [], "array index must be a non-negative integer"
                tokens.append(int(raw_index))
                index = close_index + 1
            else:
                next_dot = path.find(".", index)
                next_bracket = path.find("[", index)
                stops = [position for position in (next_dot, next_bracket) if position != -1]
                next_index = min(stops) if stops else len(path)
                key = path[index:next_index]
                if not key:
                    return [], "path has an empty segment"
                if _KEY_PATTERN.fullmatch(key) is None:
                    return [], f"unsupported object key segment: {key!r}"
                tokens.append(key)
                index = next_index

            if index == len(path):
                break
            if path[index] == ".":
                index += 1
                if index == len(path):
                    return [], "path has an empty segment"
                if path[index] in ".[":
                    return [], "path has an empty segment"
            elif path[index] == "[":
                continue
            else:
                return [], f"unexpected path character: {path[index]!r}"

        return tokens, None

    @staticmethod
    def _traverse(document: object, tokens: list[_PathToken]) -> tuple[object | None, str | None, dict[str, object]]:
        """Traverse a parsed JSON value with object-key and array-index tokens.

        Args:
            document: Parsed JSON document.
            tokens: Path tokens from :meth:`_parse_path`.

        Returns:
            Selected value, optional error, and error metadata.
        """

        current = document
        for token in tokens:
            if isinstance(token, str):
                if not isinstance(current, dict):
                    return None, f"expected object before key {token!r}", {"segment": token}
                if token not in current:
                    return None, f"key not found: {token}", {"segment": token}
                current = current[token]
                continue

            if not isinstance(current, list):
                return None, f"expected array before index {token}", {"index": token}
            if token >= len(current):
                return None, f"index out of bounds: {token}", {"index": token, "length": len(current)}
            current = current[token]

        return current, None, {}

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result.

        Args:
            message: Human-readable failure explanation.
            metadata: Structured metadata for the failure.

        Returns:
            A ``ok=False`` tool result carrying the message and metadata.
        """

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
