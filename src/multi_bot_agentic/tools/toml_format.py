"""TOML validation and canonicalization tool.

Agents often exchange configuration as TOML (for example ``pyproject.toml``
snippets or model handoff payloads). This tool parses TOML text with
``tomllib`` (Python 3.11+) or ``tomli`` when available, then re-serializes a
deterministic subset of values (tables, arrays, strings, ints, floats, bools)
without executing code. Dates/times and other non-scalar types are refused so
output stays portable across GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from typing import Final, TypeAlias

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_BARE_KEY_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_-]+\Z")

TomlScalar: TypeAlias = str | int | float | bool
TomlValue: TypeAlias = TomlScalar | list["TomlValue"] | dict[str, "TomlValue"]


class _TomlFormatError(ValueError):
    """Raised when the document cannot be parsed or serialized safely."""


class TomlFormatTool:
    """Validate and canonicalize a TOML document."""

    name = "toml_format"
    description = "Validates TOML and returns it canonicalized (sorted keys; tables/arrays/scalars only)."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Validate and canonicalize the TOML document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the TOML
                document to validate.

        Returns:
            Tool result with the canonicalized document, or ``ok=False`` and an
            explanation when the document is empty, too long, unparsable, or
            outside the supported value subset.
        """

        document = str(invocation.arguments.get("text", "")).strip()
        if not document:
            return ToolResult(tool_name=self.name, ok=False, content="document is empty", metadata={})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                metadata={"chars": len(document)},
            )

        try:
            parsed = _load_toml(document)
            normalized = _normalize_value(parsed)
            if not isinstance(normalized, dict):
                raise _TomlFormatError("top-level value must be a table")
            canonical = _dump_toml(normalized)
        except _TomlFormatError as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"invalid TOML: {error}",
                metadata={"chars": len(document)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=canonical,
            metadata={"top_level_type": "dict", "keys": len(normalized)},
        )


def _get_toml_loads() -> Callable[[str], object] | None:
    """Return a TOML ``loads`` function when a parser is available."""

    try:
        import tomllib

        return tomllib.loads
    except ImportError:
        pass

    try:
        import tomli

        return tomli.loads
    except ImportError:
        return None


def _get_toml_dumps() -> Callable[[dict[str, TomlValue]], str] | None:
    """Return a TOML ``dumps`` function when ``tomli_w`` is available."""

    try:
        import tomli_w
    except ImportError:
        return None
    return tomli_w.dumps


def _load_toml(document: str) -> object:
    """Parse TOML text with ``tomllib`` or ``tomli``."""

    loads = _get_toml_loads()
    if loads is None:
        raise _TomlFormatError("TOML parser unavailable (need Python 3.11+ tomllib or the tomli package)")
    try:
        return loads(document)
    except Exception as error:
        raise _TomlFormatError(str(error)) from error


def _normalize_value(value: object) -> TomlValue:
    """Restrict parsed values to the portable dict/list/str/int/float/bool subset."""

    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _TomlFormatError("non-finite floats are not supported")
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    raise _TomlFormatError(f"unsupported value type {type(value).__name__}")


def _dump_toml(document: dict[str, TomlValue]) -> str:
    """Serialize a normalized TOML table deterministically."""

    dumps = _get_toml_dumps()
    if dumps is not None:
        return dumps(_sort_keys(document)).rstrip("\n")

    lines: list[str] = []
    _emit_table(lines, document, path=())
    return "\n".join(lines)


def _sort_keys(value: TomlValue) -> TomlValue:
    """Recursively sort mapping keys for deterministic third-party dumps."""

    if isinstance(value, dict):
        return {key: _sort_keys(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sort_keys(item) for item in value]
    return value


def _emit_table(lines: list[str], table: dict[str, TomlValue], path: tuple[str, ...]) -> None:
    """Emit one TOML table: scalars first, then nested tables, then arrays of tables."""

    simple_keys: list[str] = []
    table_keys: list[str] = []
    aot_keys: list[str] = []
    for key, value in table.items():
        if isinstance(value, dict):
            if value:
                table_keys.append(key)
            else:
                simple_keys.append(key)
        elif _is_array_of_tables(value):
            aot_keys.append(key)
        else:
            simple_keys.append(key)

    simple_keys.sort()
    table_keys.sort()
    aot_keys.sort()

    # Skip empty intermediate headers such as ``[parent]`` when ``parent`` only
    # contains nested tables; emit ``[parent.child]`` instead.
    if path and (simple_keys or aot_keys or not table_keys):
        _append_blank_before_header(lines)
        lines.append(f"[{_format_key_path(path)}]")

    for key in simple_keys:
        lines.append(f"{_format_key(key)} = {_format_value(table[key])}")

    for key in table_keys:
        child = table[key]
        assert isinstance(child, dict)
        _emit_table(lines, child, (*path, key))

    for key in aot_keys:
        items = table[key]
        assert isinstance(items, list)
        for item in items:
            assert isinstance(item, dict)
            _append_blank_before_header(lines)
            lines.append(f"[[{_format_key_path((*path, key))}]]")
            _emit_aot_item(lines, item)


def _append_blank_before_header(lines: list[str]) -> None:
    """Insert a blank line before a table header when the buffer already has content."""

    if lines and lines[-1] != "":
        lines.append("")


def _emit_aot_item(lines: list[str], table: dict[str, TomlValue]) -> None:
    """Emit the body of one array-of-tables item (scalars and inline nested values)."""

    for key in sorted(table):
        lines.append(f"{_format_key(key)} = {_format_value(table[key])}")


def _is_array_of_tables(value: TomlValue) -> bool:
    """Return whether ``value`` should be emitted as ``[[table]]`` entries."""

    return isinstance(value, list) and bool(value) and all(isinstance(item, dict) for item in value)


def _format_key_path(path: tuple[str, ...]) -> str:
    """Format a dotted table path."""

    return ".".join(_format_key(part) for part in path)


def _format_key(key: str) -> str:
    """Format a bare or quoted TOML key."""

    return key if _BARE_KEY_RE.fullmatch(key) else _format_string(key)


def _format_value(value: TomlValue) -> str:
    """Format a TOML value in inline form."""

    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _TomlFormatError("non-finite floats are not supported")
        rendered = repr(value)
        if rendered.endswith(".0"):
            return rendered
        return rendered
    if isinstance(value, str):
        return _format_string(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format_value(item) for item in value) + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        body = ", ".join(f"{_format_key(key)} = {_format_value(value[key])}" for key in sorted(value))
        return "{ " + body + " }"
    raise _TomlFormatError(f"unsupported value type {type(value).__name__}")


def _format_string(value: str) -> str:
    """Format a basic TOML double-quoted string."""

    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\b", "\\b")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\f", "\\f")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'
