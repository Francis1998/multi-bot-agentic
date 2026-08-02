"""JSON array select / pluck query tool.

``json_path`` extracts one nested value by a fixed path. Agents also need to
filter JSON arrays or pluck a field across objects — the gap popular agent
runtimes fill with a small ``jq``-style select. Asking a language model to
filter arrays invents keys and drops matches. This tool parses JSON with the
stdlib and supports two deterministic modes: ``where`` (keep objects whose
field equals a value) and ``pluck`` (collect one field from each object). It
never executes code, never evaluates scripts, and never makes network requests.
Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import json
import math
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_RESULT_CHARS: Final[int] = 20_000
_MAX_ITEMS: Final[int] = 500
_DEFAULT_MODE: Final[str] = "where"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"where", "pluck"})
_SPLIT_SENTINEL: Final[str] = "<<<JSON_QUERY>>>"


def _reject_non_finite(token: str) -> float:
    """Reject non-standard JSON constants accepted by Python's JSON decoder."""

    raise ValueError(f"{token} is not valid JSON")


def _parse_finite_float(token: str) -> float:
    """Parse a JSON float literal and reject non-finite overflows."""

    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"{token} overflows to a non-finite number and is not valid JSON")
    return value


class JsonQueryTool:
    """Filter or pluck fields from a JSON array of objects."""

    name = "json_query"
    description = (
        "Filters JSON object arrays (where field==value) or plucks a field "
        "(mode where|pluck; text+args or <<<JSON_QUERY>>>); bounded, no exec."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Filter or pluck values from a JSON array.

        Args:
            invocation: Tool invocation whose arguments hold ``text`` plus
                ``mode`` / ``field`` / optional ``equals``, or ``text`` split on
                ``<<<JSON_QUERY>>>`` with a JSON args object after the sentinel.

        Returns:
            Tool result whose ``content`` is canonical JSON, or ``ok=False``
            when input is empty, oversized, malformed, or arguments are invalid.
        """

        document, mode, field, equals, equals_provided = self._resolve_arguments(invocation)
        if document is None:
            return self._fail("text is empty", {})
        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )
        if mode not in _ALLOWED_MODES:
            return self._fail(
                f"unsupported mode: {mode!r}; must be where or pluck",
                {"mode": mode},
            )
        if not field:
            return self._fail("field is required", {"mode": mode})
        if mode == "where" and not equals_provided:
            return self._fail("where mode requires equals", {"mode": mode, "field": field})

        try:
            payload = json.loads(
                document,
                parse_constant=_reject_non_finite,
                parse_float=_parse_finite_float,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return self._fail(f"invalid JSON: {exc}", {"mode": mode})

        if not isinstance(payload, list):
            return self._fail("JSON root must be an array", {"mode": mode})
        if len(payload) > _MAX_ITEMS:
            return self._fail(
                f"array exceeds max_items={_MAX_ITEMS}",
                {"items": len(payload)},
            )

        if mode == "where":
            result: list[object] = []
            for item in payload:
                if not isinstance(item, dict):
                    return self._fail("where mode requires an array of objects", {"mode": mode})
                if field in item and item[field] == equals:
                    result.append(item)
        else:
            result = []
            for item in payload:
                if not isinstance(item, dict):
                    return self._fail("pluck mode requires an array of objects", {"mode": mode})
                result.append(item.get(field))

        content = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        if len(content) > _MAX_RESULT_CHARS:
            return self._fail(
                f"result exceeds max_chars={_MAX_RESULT_CHARS}",
                {"chars": len(content)},
            )
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "mode": mode,
                "field": field,
                "items": len(result),
                "chars": len(content),
            },
        )

    def _resolve_arguments(self, invocation: ToolInvocation) -> tuple[str | None, str, str, object, bool]:
        """Resolve document and query args from invocation or sentinel payload."""

        raw_text = str(invocation.arguments.get("text", ""))
        mode = str(invocation.arguments.get("mode", _DEFAULT_MODE)).strip().lower()
        field = str(invocation.arguments.get("field", "")).strip()
        equals_provided = "equals" in invocation.arguments
        equals: object = invocation.arguments.get("equals")

        if _SPLIT_SENTINEL in raw_text:
            document, _, args_blob = raw_text.partition(_SPLIT_SENTINEL)
            try:
                args_payload = json.loads(
                    args_blob,
                    parse_constant=_reject_non_finite,
                    parse_float=_parse_finite_float,
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                return document, mode, field, equals, equals_provided
            if isinstance(args_payload, dict):
                if "mode" in args_payload:
                    mode = str(args_payload.get("mode", mode)).strip().lower()
                if "field" in args_payload:
                    field = str(args_payload.get("field", field)).strip()
                if "equals" in args_payload:
                    equals = args_payload.get("equals")
                    equals_provided = True
            return document, mode, field, equals, equals_provided

        return raw_text, mode, field, equals, equals_provided

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
