"""YAML validation and canonicalization tool.

YAML is useful for model-authored configuration snippets, but the full language
includes aliases, tags, merge keys, and other features that are unnecessary for
agent handoffs. This tool intentionally supports a small safe subset: block
mappings, block sequences, JSON-style flow collections, and scalar
strings/numbers/booleans/null. It validates that subset and serializes it into a
deterministic, human-readable YAML form without executing code or importing a
YAML runtime.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Final, TypeAlias

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_INT_RE: Final[re.Pattern[str]] = re.compile(r"[-+]?(?:0|[1-9][0-9]*)\Z")
_FLOAT_RE: Final[re.Pattern[str]] = re.compile(
    r"[-+]?(?:(?:[0-9]+\.[0-9]*)|(?:\.[0-9]+)|(?:[0-9]+))(?:[eE][-+]?[0-9]+)\Z|"
    r"[-+]?(?:[0-9]+\.[0-9]*|\.[0-9]+)\Z"
)
_UNSUPPORTED_PLAIN_PREFIXES: Final[tuple[str, ...]] = ("&", "*", "!", "|", ">", "%", "@", "`")
_RESERVED_SCALARS: Final[frozenset[str]] = frozenset({"null", "~", "true", "false"})

Scalar: TypeAlias = str | int | float | bool | None
YamlValue: TypeAlias = Scalar | list["YamlValue"] | dict[str, "YamlValue"]


@dataclass(frozen=True)
class _Line:
    """A non-empty, comment-stripped YAML line."""

    number: int
    indent: int
    content: str


class _YamlSubsetError(ValueError):
    """Raised when the document is outside the supported YAML subset."""


class YamlFormatTool:
    """Validate and canonicalize a safe YAML subset."""

    name = "yaml_format"
    description = (
        "Validates a safe YAML subset and returns it canonicalized (sorted mapping keys, 2-space indentation)."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Validate and canonicalize the YAML document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the YAML
                document to validate.

        Returns:
            Tool result with the canonicalized document, or ``ok=False`` and an
            explanation when the document is empty, too long, or invalid YAML for
            the supported safe subset.
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
            parsed = _YamlSubsetParser(document).parse()
            canonical = _dump_yaml(parsed)
        except _YamlSubsetError as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"invalid YAML: {error}",
                metadata={"chars": len(document)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=canonical,
            metadata={"top_level_type": type(parsed).__name__},
        )


class _YamlSubsetParser:
    """Recursive-descent parser for the supported YAML subset."""

    def __init__(self, document: str) -> None:
        self._lines = _prepare_lines(document)

    def parse(self) -> YamlValue:
        """Parse the full document."""

        if not self._lines:
            raise _YamlSubsetError("document is empty")
        value, index = self._parse_block(0, self._lines[0].indent)
        if index != len(self._lines):
            line = self._lines[index]
            raise _YamlSubsetError(f"line {line.number}: unexpected content")
        return value

    def _parse_block(self, index: int, indent: int) -> tuple[YamlValue, int]:
        """Parse a mapping, sequence, or single scalar starting at ``index``."""

        line = self._lines[index]
        if line.indent != indent:
            raise _YamlSubsetError(f"line {line.number}: unexpected indentation")
        if line.content[0] in "[{":
            if index != len(self._lines) - 1:
                raise _YamlSubsetError(f"line {line.number}: flow collections must fit on one line")
            return _parse_scalar(line.content, line.number), index + 1
        if _is_sequence_item(line.content):
            return self._parse_sequence(index, indent)
        if _split_key_value(line.content) is not None:
            return self._parse_mapping(index, indent)

        if index != len(self._lines) - 1:
            raise _YamlSubsetError(f"line {line.number}: expected 'key: value' or '- value'")
        return _parse_scalar(line.content, line.number), index + 1

    def _parse_mapping(self, index: int, indent: int) -> tuple[dict[str, YamlValue], int]:
        """Parse mapping entries at one indentation level."""

        values: dict[str, YamlValue] = {}
        while index < len(self._lines):
            line = self._lines[index]
            if line.indent < indent:
                break
            if line.indent > indent:
                raise _YamlSubsetError(f"line {line.number}: unexpected indentation")
            if _is_sequence_item(line.content):
                raise _YamlSubsetError(f"line {line.number}: cannot mix sequence items with mapping entries")

            split = _split_key_value(line.content)
            if split is None:
                raise _YamlSubsetError(f"line {line.number}: expected 'key: value'")
            raw_key, raw_value = split
            key = _parse_key(raw_key, line.number)
            if key in values:
                raise _YamlSubsetError(f"line {line.number}: duplicate key {key!r}")

            index += 1
            if raw_value:
                values[key] = _parse_scalar(raw_value, line.number)
                continue

            if index < len(self._lines) and self._lines[index].indent > indent:
                values[key], index = self._parse_block(index, self._lines[index].indent)
            else:
                values[key] = None

        return values, index

    def _parse_sequence(self, index: int, indent: int) -> tuple[list[YamlValue], int]:
        """Parse sequence entries at one indentation level."""

        values: list[YamlValue] = []
        while index < len(self._lines):
            line = self._lines[index]
            if line.indent < indent:
                break
            if line.indent > indent:
                raise _YamlSubsetError(f"line {line.number}: unexpected indentation")
            if not _is_sequence_item(line.content):
                raise _YamlSubsetError(f"line {line.number}: cannot mix mapping entries with sequence items")

            raw_value = line.content[1:].strip()
            index += 1
            if raw_value:
                values.append(_parse_scalar(raw_value, line.number))
                continue

            if index < len(self._lines) and self._lines[index].indent > indent:
                value, index = self._parse_block(index, self._lines[index].indent)
                values.append(value)
            else:
                values.append(None)

        return values, index


def _prepare_lines(document: str) -> list[_Line]:
    """Normalize, strip comments, and validate leading whitespace."""

    lines: list[_Line] = []
    for number, raw_line in enumerate(document.replace("\r\n", "\n").replace("\r", "\n").split("\n"), start=1):
        if raw_line.lstrip(" ").startswith(("---", "...")):
            raise _YamlSubsetError(f"line {number}: document markers are not supported")
        if raw_line[: len(raw_line) - len(raw_line.lstrip())].find("\t") != -1:
            raise _YamlSubsetError(f"line {number}: tabs are not allowed for indentation")

        content = _strip_comment(raw_line).rstrip()
        if not content.strip():
            continue
        indent = len(content) - len(content.lstrip(" "))
        lines.append(_Line(number=number, indent=indent, content=content.strip()))
    return lines


def _strip_comment(line: str) -> str:
    """Strip YAML comments that begin outside quoted scalars."""

    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if quote == '"':
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if quote == "'":
            if char == quote:
                if index + 1 < len(line) and line[index + 1] == quote:
                    continue
                quote = None
            continue

        if char in {"'", '"'}:
            quote = char
        elif char == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index]
    return line


def _is_sequence_item(content: str) -> bool:
    """Return whether a line is a supported sequence item."""

    return content == "-" or content.startswith("- ")


def _split_key_value(content: str) -> tuple[str, str] | None:
    """Split ``key: value`` while ignoring colons inside quoted strings."""

    quote: str | None = None
    escaped = False
    for index, char in enumerate(content):
        if quote == '"':
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if quote == "'":
            if char == quote:
                if index + 1 < len(content) and content[index + 1] == quote:
                    continue
                quote = None
            continue

        if char in {"'", '"'}:
            quote = char
        elif char == ":" and (index == len(content) - 1 or content[index + 1].isspace()):
            key = content[:index].strip()
            value = content[index + 1 :].strip()
            return key, value
    return None


def _parse_key(raw_key: str, line_number: int) -> str:
    """Parse a mapping key as a scalar string."""

    if not raw_key:
        raise _YamlSubsetError(f"line {line_number}: mapping key is empty")
    key = _parse_scalar(raw_key, line_number)
    if isinstance(key, (dict, list)):
        raise _YamlSubsetError(f"line {line_number}: mapping key must be a scalar")
    if key is None:
        raise _YamlSubsetError(f"line {line_number}: mapping key cannot be null")
    return str(key)


def _parse_scalar(text: str, line_number: int) -> YamlValue:
    """Parse a scalar or JSON-style flow collection."""

    if not text:
        return ""
    if text[0] in "[{":
        return _parse_json_flow(text, line_number)
    if text[0] in "]}":
        raise _YamlSubsetError(f"line {line_number}: unmatched flow collection delimiter")
    if text.startswith('"'):
        return _parse_double_quoted(text, line_number)
    if text.startswith("'"):
        return _parse_single_quoted(text, line_number)

    lowered = text.lower()
    if lowered in {"null", "~"}:
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if _INT_RE.fullmatch(text):
        return int(text)
    if _FLOAT_RE.fullmatch(text):
        value = float(text)
        if not math.isfinite(value):
            raise _YamlSubsetError(f"line {line_number}: non-finite floats are not supported")
        return value

    if text.startswith(_UNSUPPORTED_PLAIN_PREFIXES):
        raise _YamlSubsetError(f"line {line_number}: unsupported YAML feature")
    if ": " in text:
        raise _YamlSubsetError(f"line {line_number}: plain scalars cannot contain ': '")
    return text


def _parse_json_flow(text: str, line_number: int) -> YamlValue:
    """Parse a JSON-style flow collection."""

    try:
        value = json.loads(text, parse_constant=_reject_non_finite, parse_float=_parse_finite_float)
    except (json.JSONDecodeError, ValueError) as error:
        raise _YamlSubsetError(f"line {line_number}: invalid flow collection: {error}") from error
    return _ensure_yaml_value(value, line_number)


def _parse_double_quoted(text: str, line_number: int) -> str:
    """Parse a JSON-compatible double-quoted string."""

    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise _YamlSubsetError(f"line {line_number}: invalid double-quoted string: {error}") from error
    if not isinstance(value, str):
        raise _YamlSubsetError(f"line {line_number}: quoted value must be a string")
    return value


def _parse_single_quoted(text: str, line_number: int) -> str:
    """Parse a minimal YAML single-quoted string."""

    if len(text) < 2 or not text.endswith("'"):
        raise _YamlSubsetError(f"line {line_number}: unterminated single-quoted string")
    return text[1:-1].replace("''", "'")


def _reject_non_finite(token: str) -> float:
    """Reject JSON's non-standard non-finite constants."""

    raise ValueError(f"{token} is not valid in YAML safe subset")


def _parse_finite_float(token: str) -> float:
    """Parse finite JSON float tokens."""

    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"{token} overflows to a non-finite number")
    return value


def _ensure_yaml_value(value: object, line_number: int) -> YamlValue:
    """Validate that JSON flow data fits the YAML subset value model."""

    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and not math.isfinite(value):
            raise _YamlSubsetError(f"line {line_number}: non-finite floats are not supported")
        return value
    if isinstance(value, list):
        return [_ensure_yaml_value(item, line_number) for item in value]
    if isinstance(value, dict):
        return {str(key): _ensure_yaml_value(item, line_number) for key, item in value.items()}
    raise _YamlSubsetError(f"line {line_number}: unsupported flow value")


def _dump_yaml(value: YamlValue, indent: int = 0) -> str:
    """Serialize a parsed YAML subset value deterministically."""

    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return f"{prefix}{{}}"
        lines: list[str] = []
        for key in sorted(value):
            item = value[key]
            rendered_key = _render_key(key)
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{prefix}{rendered_key}:")
                lines.append(_dump_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{rendered_key}: {_render_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{prefix}[]"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{prefix}-")
                lines.append(_dump_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_render_scalar(item)}")
        return "\n".join(lines)
    return f"{prefix}{_render_scalar(value)}"


def _render_key(key: str) -> str:
    """Render a mapping key."""

    return key if _is_plain_string(key) else json.dumps(key, ensure_ascii=False)


def _render_scalar(value: YamlValue) -> str:
    """Render a scalar or empty collection inline."""

    if isinstance(value, dict):
        return "{}"
    if isinstance(value, list):
        return "[]"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return json.dumps(value)
    return value if _is_plain_string(value) else json.dumps(value, ensure_ascii=False)


def _is_plain_string(value: str) -> bool:
    """Return whether a string can be emitted as a safe plain scalar."""

    if not value or value != value.strip():
        return False
    lowered = value.lower()
    if lowered in _RESERVED_SCALARS:
        return False
    if value.startswith(_UNSUPPORTED_PLAIN_PREFIXES) or value.startswith(("- ", "? ", ": ")):
        return False
    return not any(marker in value for marker in ("#", ": ", "\n", "\t", "[", "]", "{", "}"))
