"""Deterministic bounded JSON difference-path tool.

Agents sometimes need to identify where two JSON observations differ without
copying both documents into the next model turn. This tool parses two bounded
documents with the standard library and returns sorted dotted/bracket paths such
as ``models[0].name``. It never executes code or makes network requests. Safe
for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Documents may be supplied as separate ``text`` / ``other`` arguments or as one
``text`` value split on ``<<<JSON_DIFF_PATHS>>>``.
"""

from __future__ import annotations

import json
import math
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_PATHS: Final[int] = 2000
_MAX_OUTPUT_CHARS: Final[int] = 20_000
_SPLIT_SENTINEL: Final[str] = "<<<JSON_DIFF_PATHS>>>"


def _reject_non_finite(token: str) -> float:
    """Reject non-standard JSON constants accepted by Python's decoder."""

    raise ValueError(f"{token} is not valid JSON")


def _parse_finite_float(token: str) -> float:
    """Parse a JSON float and reject overflow to infinity."""

    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"{token} overflows to a non-finite number and is not valid JSON")
    return value


class JsonDiffPathsTool:
    """Return sorted dotted/bracket paths whose JSON values differ."""

    name = "json_diff_paths"
    description = (
        "Compares two JSON documents and returns sorted differing dotted/bracket paths; "
        "accepts text+other or <<<JSON_DIFF_PATHS>>>; max 20_000 chars per document and 2000 paths."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse two JSON documents and report their differing paths."""

        left_text, right_text, resolve_error = self._resolve_documents(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert left_text is not None and right_text is not None

        for label, document in (("text", left_text), ("other", right_text)):
            if not document.strip():
                return self._fail(f"{label} is empty", {})
            if len(document) > _MAX_DOCUMENT_CHARS:
                return self._fail(
                    f"{label} exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                    {"chars": len(document), "document": label},
                )

        left, parse_error = self._parse_document(left_text, "text")
        if parse_error is not None:
            return self._fail(parse_error[0], parse_error[1])
        right, parse_error = self._parse_document(right_text, "other")
        if parse_error is not None:
            return self._fail(parse_error[0], parse_error[1])

        paths, exceeded = _different_paths(left, right)
        if exceeded:
            return self._fail(f"diff exceeds max_paths={_MAX_PATHS}", {"paths": _MAX_PATHS})

        content = json.dumps(paths, indent=2, ensure_ascii=False) + "\n"
        if len(content) > _MAX_OUTPUT_CHARS:
            return self._fail(
                f"diff output exceeds max_chars={_MAX_OUTPUT_CHARS}",
                {"chars": len(content), "paths": len(paths)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "paths": len(paths),
                "text_chars": len(left_text),
                "other_chars": len(right_text),
            },
        )

    @staticmethod
    def _resolve_documents(
        arguments: dict[str, object],
    ) -> tuple[str | None, str | None, str | None]:
        """Resolve documents from explicit arguments or sentinel syntax."""

        text = str(arguments.get("text", ""))
        if "other" in arguments:
            return text, str(arguments["other"]), None
        if _SPLIT_SENTINEL not in text:
            return text, "", None

        left, right = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in right:
            return None, None, "text contains more than one <<<JSON_DIFF_PATHS>>> sentinel"
        return left, right, None

    @staticmethod
    def _parse_document(
        document: str,
        label: str,
    ) -> tuple[object | None, tuple[str, dict[str, object]] | None]:
        """Parse one strict JSON document."""

        try:
            parsed = json.loads(
                document,
                parse_constant=_reject_non_finite,
                parse_float=_parse_finite_float,
            )
        except json.JSONDecodeError as exc:
            return None, (f"invalid JSON in {label}: {exc.msg}", {"document": label, "position": exc.pos})
        except (RecursionError, ValueError) as exc:
            return None, (f"invalid JSON in {label}: {exc}", {"document": label})
        return parsed, None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _different_paths(left: object, right: object) -> tuple[list[str], bool]:
    """Collect differing paths iteratively, stopping above the path cap."""

    paths: list[str] = []
    stack: list[tuple[object, object, str]] = [(left, right, "")]

    while stack:
        left_value, right_value, path = stack.pop()
        if type(left_value) is not type(right_value):
            paths.append(path or "$")
        elif isinstance(left_value, dict) and isinstance(right_value, dict):
            left_keys = set(left_value)
            right_keys = set(right_value)
            for key in sorted(left_keys ^ right_keys, reverse=True):
                paths.append(_object_path(path, key))
                if len(paths) > _MAX_PATHS:
                    return [], True
            for key in sorted(left_keys & right_keys, reverse=True):
                stack.append((left_value[key], right_value[key], _object_path(path, key)))
        elif isinstance(left_value, list) and isinstance(right_value, list):
            shared_length = min(len(left_value), len(right_value))
            for index in range(max(len(left_value), len(right_value)) - 1, shared_length - 1, -1):
                paths.append(_array_path(path, index))
                if len(paths) > _MAX_PATHS:
                    return [], True
            for index in range(shared_length - 1, -1, -1):
                stack.append((left_value[index], right_value[index], _array_path(path, index)))
        elif left_value != right_value:
            paths.append(path or "$")

        if len(paths) > _MAX_PATHS:
            return [], True

    paths.sort()
    return paths, False


def _object_path(prefix: str, key: str) -> str:
    """Append an object key using the json_flatten dotted convention."""

    return f"{prefix}.{key}" if prefix else key


def _array_path(prefix: str, index: int) -> str:
    """Append an array index using bracket notation."""

    return f"{prefix}[{index}]" if prefix else f"[{index}]"
