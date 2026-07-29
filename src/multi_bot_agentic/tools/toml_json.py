"""TOML ↔ JSON bridge tool for agent handoffs.

Agents often need to convert configuration between TOML (common in
``pyproject.toml`` snippets) and JSON (common in API payloads). This tool
parses one format and emits the other using the same portable value subset as
``toml_format`` and ``json_format``: dict/list/str/int/float/bool only. Dates,
nulls, and non-finite numbers are refused so output stays portable across
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import json
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult
from multi_bot_agentic.tools.json_format import _parse_finite_float, _reject_non_finite
from multi_bot_agentic.tools.toml_format import (
    TomlValue,
    _dump_toml,
    _load_toml,
    _normalize_value,
    _TomlFormatError,
)

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_VALID_DIRECTIONS: Final[frozenset[str]] = frozenset({"to_json", "to_toml"})


class _TomlJsonError(ValueError):
    """Raised when the document cannot be converted safely."""


class TomlJsonTool:
    """Convert between TOML and JSON text."""

    name = "toml_json"
    description = (
        "Converts between TOML and JSON text for agent handoffs "
        "(direction: to_json or to_toml; portable dict/list/str/int/float/bool subset)."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Convert the document between TOML and JSON.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the source
                document and optional ``direction`` (``to_json`` default or
                ``to_toml``).

        Returns:
            Tool result with converted text, or ``ok=False`` and an explanation
            when the document is empty, too long, invalid, or outside the
            supported value subset.
        """

        document = str(invocation.arguments.get("text", "")).strip()
        direction = str(invocation.arguments.get("direction", "to_json")).strip().lower()
        if not document:
            return ToolResult(tool_name=self.name, ok=False, content="document is empty", metadata={})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                metadata={"chars": len(document)},
            )
        if direction not in _VALID_DIRECTIONS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="invalid direction: must be to_json or to_toml",
                metadata={"direction": direction},
            )

        if direction == "to_json":
            return self._to_json(document)
        return self._to_toml(document)

    def _to_json(self, document: str) -> ToolResult:
        """Parse TOML and emit canonical JSON."""

        try:
            parsed = _load_toml(document)
            normalized = _normalize_value(parsed)
        except _TomlFormatError as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"invalid TOML: {error}",
                metadata={"direction": "to_json", "chars": len(document)},
            )

        content = json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={"direction": "to_json", "top_level_type": type(normalized).__name__},
        )

    def _to_toml(self, document: str) -> ToolResult:
        """Parse JSON and emit canonical TOML."""

        try:
            parsed = json.loads(
                document,
                parse_constant=_reject_non_finite,
                parse_float=_parse_finite_float,
            )
            normalized = _normalize_json_value(parsed)
            if not isinstance(normalized, dict):
                raise _TomlJsonError("top-level value must be a table")
            content = _dump_toml(normalized)
        except (json.JSONDecodeError, ValueError) as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"invalid JSON: {error}",
                metadata={"direction": "to_toml", "chars": len(document)},
            )
        except (_TomlFormatError, _TomlJsonError) as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"invalid JSON: {error}",
                metadata={"direction": "to_toml", "chars": len(document)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={"direction": "to_toml", "top_level_type": "dict", "keys": len(normalized)},
        )


def _normalize_json_value(value: object) -> TomlValue:
    """Restrict parsed JSON values to the portable TOML-compatible subset."""

    if value is None:
        raise _TomlJsonError("null is not supported in TOML")
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_json_value(item) for key, item in value.items()}
    return _normalize_value(value)
