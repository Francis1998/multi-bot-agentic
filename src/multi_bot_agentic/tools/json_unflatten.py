"""Deterministic JSON unflattening tool.

Agents often need a flat key/value map rebuilt into nested JSON before the next
model turn. Asking a model to reconstruct dotted and bracketed paths is brittle:
paths can conflict, array indexes can be dropped, and separators can be applied
inconsistently. This tool parses JSON with the standard library and rebuilds
paths such as ``a.b[0].c`` with a configurable object separator. It never
executes code or makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_KEYS: Final[int] = 2000
_MAX_ARRAY_INDEX: Final[int] = _MAX_KEYS - 1
_MAX_PATH_DEPTH: Final[int] = 100
_DEFAULT_SEPARATOR: Final[str] = "."
_MISSING: Final[object] = object()


def _reject_non_finite(token: str) -> float:
    """Reject non-standard JSON constants accepted by Python's JSON decoder."""

    raise ValueError(f"{token} is not valid JSON")


def _parse_finite_float(token: str) -> float:
    """Parse a JSON float literal and reject values that overflow to infinity."""

    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"{token} overflows to a non-finite number and is not valid JSON")
    return value


class JsonUnflattenTool:
    """Rebuild nested JSON from dotted/bracket flat keys."""

    name = "json_unflatten"
    description = (
        "Rebuilds nested JSON from dotted/bracket flat keys (separator default .); "
        "max 20_000 chars input and 2000 keys."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Unflatten a JSON object containing flat path keys."""

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

        if not isinstance(parsed, dict):
            return self._fail("JSON root must be an object", {})
        if len(parsed) > _MAX_KEYS:
            return self._fail(
                f"flat object exceeds max_keys={_MAX_KEYS}",
                {"keys": len(parsed)},
            )

        root = _PathNode()
        try:
            for key, value in parsed.items():
                path = _parse_path(key, separator)
                _insert_path(root, path, value, key)
            rebuilt = _render_node(root)
        except _UnflattenError as exc:
            return self._fail(str(exc), {"keys": len(parsed), "separator": separator})

        content = json.dumps(rebuilt, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if len(content) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"unflatten output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(content), "keys": len(parsed)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "keys": len(parsed),
                "separator": separator,
                "chars": len(content),
                "input_chars": len(document),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


class _UnflattenError(ValueError):
    """Raised when a flat key cannot be safely reconstructed."""


@dataclass
class _PathNode:
    """One node in the validated flat-key path tree."""

    value: object = _MISSING
    children: dict[str | int, _PathNode] = field(default_factory=dict)
    child_kind: type[str] | type[int] | None = None


def _parse_path(key: str, separator: str) -> list[str | int]:
    """Parse one dotted/bracket key into object and array path components."""

    if not key:
        raise _UnflattenError("flat keys must be non-empty")

    path: list[str | int] = []
    position = 0
    expect_object_key = not key.startswith("[")
    while position < len(key):
        if expect_object_key:
            start = position
            while position < len(key) and not key.startswith(separator, position) and key[position] != "[":
                if key[position] == "]":
                    raise _UnflattenError(f"invalid bracket syntax in key {key!r}")
                position += 1
            if position == start:
                raise _UnflattenError(f"empty path segment in key {key!r}")
            path.append(key[start:position])

        while position < len(key) and key[position] == "[":
            close = key.find("]", position + 1)
            if close < 0:
                raise _UnflattenError(f"unterminated array index in key {key!r}")
            index_text = key[position + 1 : close]
            if not index_text.isdigit():
                raise _UnflattenError(f"array indexes must be non-negative integers in key {key!r}")
            index = int(index_text)
            if index > _MAX_ARRAY_INDEX:
                raise _UnflattenError(f"array index exceeds max_index={_MAX_ARRAY_INDEX} in key {key!r}")
            path.append(index)
            position = close + 1

        if position == len(key):
            break
        if not key.startswith(separator, position):
            raise _UnflattenError(f"invalid path syntax in key {key!r}")
        position += len(separator)
        if position == len(key) or key[position] == "[":
            raise _UnflattenError(f"empty path segment in key {key!r}")
        expect_object_key = True

        if len(path) >= _MAX_PATH_DEPTH:
            raise _UnflattenError(f"path exceeds max_depth={_MAX_PATH_DEPTH} in key {key!r}")

    if not path:
        raise _UnflattenError(f"invalid flat key {key!r}")
    if len(path) > _MAX_PATH_DEPTH:
        raise _UnflattenError(f"path exceeds max_depth={_MAX_PATH_DEPTH} in key {key!r}")
    return path


def _insert_path(root: _PathNode, path: list[str | int], value: object, source_key: str) -> None:
    """Insert one parsed path while rejecting prefix and container conflicts."""

    node = root
    for component in path:
        if node.value is not _MISSING:
            raise _UnflattenError(f"conflicting key paths at {source_key!r}")
        component_kind = type(component)
        if node.child_kind is not None and node.child_kind is not component_kind:
            raise _UnflattenError(f"conflicting object/array paths at {source_key!r}")
        node.child_kind = component_kind
        node = node.children.setdefault(component, _PathNode())

    if node.value is not _MISSING or node.children:
        raise _UnflattenError(f"conflicting key paths at {source_key!r}")
    node.value = value


def _render_node(node: _PathNode) -> object:
    """Render a validated path tree as JSON-compatible containers."""

    if node.value is not _MISSING:
        return node.value
    if node.child_kind is str:
        return {str(key): _render_node(child) for key, child in node.children.items()}
    if node.child_kind is int:
        largest_index = max(int(key) for key in node.children)
        result: list[object] = [None] * (largest_index + 1)
        for key, child in node.children.items():
            result[int(key)] = _render_node(child)
        return result
    return {}
