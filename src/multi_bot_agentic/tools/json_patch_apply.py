"""Deterministic bounded RFC 6902 JSON Patch application tool.

Agents often need to apply structured updates without asking a model to
reconstruct an entire JSON document. This tool implements RFC 6902
``add``, ``remove``, ``replace``, ``move``, ``copy``, and ``test`` operations
with stdlib :mod:`json` only. It bounds both inputs, operation count, and output,
and never executes code or makes network requests. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Inputs may be supplied as separate ``text`` / ``patch`` arguments or as one
``text`` value split on ``<<<JSON_PATCH>>>``.
"""

from __future__ import annotations

import copy
import json
import math
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_PATCH_CHARS: Final[int] = 20_000
_MAX_OUTPUT_CHARS: Final[int] = 20_000
_MAX_OPERATIONS: Final[int] = 200
_SPLIT_SENTINEL: Final[str] = "<<<JSON_PATCH>>>"
_OPERATIONS: Final[frozenset[str]] = frozenset({"add", "remove", "replace", "move", "copy", "test"})


class _PatchError(ValueError):
    """Raised for an invalid operation or failed patch application."""


def _reject_non_finite(token: str) -> float:
    """Reject non-standard JSON constants accepted by Python's decoder."""

    raise ValueError(f"{token} is not valid JSON")


def _parse_finite_float(token: str) -> float:
    """Parse a JSON float while rejecting overflow to infinity."""

    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"{token} overflows to a non-finite number and is not valid JSON")
    return value


class JsonPatchApplyTool:
    """Apply a bounded RFC 6902 JSON Patch to a JSON document."""

    name = "json_patch_apply"
    description = (
        "Applies RFC 6902 add/remove/replace/move/copy/test operations to JSON; "
        "accepts text+patch or <<<JSON_PATCH>>>; max 20_000 chars and 200 operations."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse and atomically apply the requested JSON Patch."""

        document_raw, patch_raw, resolve_error = self._resolve_inputs(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document_raw is not None and patch_raw is not None

        if not document_raw.strip():
            return self._fail("text JSON document is empty", {})
        if not patch_raw.strip():
            return self._fail("patch JSON array is empty", {})
        if len(document_raw) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document_raw), "document": "text"},
            )
        if len(patch_raw) > _MAX_PATCH_CHARS:
            return self._fail(
                f"patch exceeds max_chars={_MAX_PATCH_CHARS}",
                {"chars": len(patch_raw), "document": "patch"},
            )

        document, parse_error = self._parse_json(document_raw, "text")
        if parse_error is not None:
            return self._fail(parse_error[0], parse_error[1])
        patch, parse_error = self._parse_json(patch_raw, "patch")
        if parse_error is not None:
            return self._fail(parse_error[0], parse_error[1])
        if not isinstance(patch, list):
            return self._fail("patch must be a JSON array", {"patch_type": type(patch).__name__})
        if len(patch) > _MAX_OPERATIONS:
            return self._fail(
                f"patch exceeds max_operations={_MAX_OPERATIONS}",
                {"operations": len(patch)},
            )

        try:
            result = _clone(document)
        except _PatchError as exc:
            return self._fail(str(exc), {})

        for index, operation in enumerate(patch):
            if not isinstance(operation, dict):
                return self._fail(
                    f"operation {index} must be an object",
                    {"operation_index": index, "operation_type": type(operation).__name__},
                )
            try:
                result = _apply_operation(result, operation)
            except _PatchError as exc:
                return self._fail(
                    f"operation {index} failed: {exc}",
                    {"operation_index": index, "op": operation.get("op")},
                )

        try:
            content = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
        except (RecursionError, TypeError, ValueError) as exc:
            return self._fail(f"patched result is not serializable JSON: {exc}", {})
        if len(content) > _MAX_OUTPUT_CHARS:
            return self._fail(
                f"patched output exceeds max_chars={_MAX_OUTPUT_CHARS}",
                {"chars": len(content), "operations": len(patch)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "chars": len(content),
                "input_chars": len(document_raw),
                "operations": len(patch),
                "patch_chars": len(patch_raw),
            },
        )

    @staticmethod
    def _resolve_inputs(
        arguments: dict[str, object],
    ) -> tuple[str | None, str | None, str | None]:
        """Resolve document and patch JSON from arguments or sentinel syntax."""

        text = str(arguments.get("text", ""))
        if "patch" in arguments:
            patch_argument = arguments["patch"]
            if isinstance(patch_argument, str):
                return text, patch_argument, None
            try:
                patch_text = json.dumps(patch_argument, ensure_ascii=False, allow_nan=False)
            except (RecursionError, TypeError, ValueError) as exc:
                return None, None, f"patch is not JSON serializable: {exc}"
            return text, patch_text, None

        if _SPLIT_SENTINEL not in text:
            return text, "", None
        document, patch_text = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in patch_text:
            return None, None, "text contains more than one <<<JSON_PATCH>>> sentinel"
        return document, patch_text, None

    @staticmethod
    def _parse_json(
        raw: str,
        label: str,
    ) -> tuple[object | None, tuple[str, dict[str, object]] | None]:
        """Parse strict finite JSON and return structured failure details."""

        try:
            value = json.loads(
                raw,
                parse_constant=_reject_non_finite,
                parse_float=_parse_finite_float,
            )
        except json.JSONDecodeError as exc:
            return None, (f"invalid JSON in {label}: {exc.msg}", {"document": label, "position": exc.pos})
        except (RecursionError, ValueError) as exc:
            return None, (f"invalid JSON in {label}: {exc}", {"document": label})
        return value, None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _apply_operation(document: object, operation: dict[object, object]) -> object:
    """Apply one validated JSON Patch operation."""

    op = operation.get("op")
    if not isinstance(op, str) or op not in _OPERATIONS:
        raise _PatchError(f"op must be one of {', '.join(sorted(_OPERATIONS))}")
    path = _required_string(operation, "path")

    if op == "add":
        return _add(document, path, _required_member(operation, "value"))
    if op == "remove":
        updated, _removed = _remove(document, path)
        return updated
    if op == "replace":
        _get(document, path)
        return _replace(document, path, _required_member(operation, "value"))
    if op == "copy":
        source = _required_string(operation, "from")
        return _add(document, path, _clone(_get(document, source)))
    if op == "move":
        source = _required_string(operation, "from")
        source_tokens = _parse_pointer(source)
        destination_tokens = _parse_pointer(path)
        if len(destination_tokens) > len(source_tokens) and destination_tokens[: len(source_tokens)] == source_tokens:
            raise _PatchError("move path cannot be a child of from")
        updated, moved = _remove(document, source)
        return _add(updated, path, moved)

    expected = _required_member(operation, "value")
    actual = _get(document, path)
    if not _json_equal(actual, expected):
        raise _PatchError(f"test did not match value at path {path!r}")
    return document


def _required_string(operation: dict[object, object], member: str) -> str:
    """Return one required string operation member."""

    value = _required_member(operation, member)
    if not isinstance(value, str):
        raise _PatchError(f"{member!r} must be a string")
    return value


def _required_member(operation: dict[object, object], member: str) -> object:
    """Return one required operation member, preserving explicit null."""

    if member not in operation:
        raise _PatchError(f"missing required member {member!r}")
    return operation[member]


def _parse_pointer(pointer: str) -> list[str]:
    """Parse an RFC 6901 JSON Pointer used by RFC 6902."""

    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise _PatchError("path must be empty or start with '/'")

    tokens: list[str] = []
    for raw_token in pointer.split("/")[1:]:
        index = 0
        while index < len(raw_token):
            if raw_token[index] != "~":
                index += 1
                continue
            if index + 1 >= len(raw_token) or raw_token[index + 1] not in {"0", "1"}:
                raise _PatchError(f"invalid JSON Pointer escape in token {raw_token!r}")
            index += 2
        tokens.append(raw_token.replace("~1", "/").replace("~0", "~"))
    return tokens


def _get(document: object, pointer: str) -> object:
    """Return the value at a JSON Pointer or raise a patch error."""

    current = document
    for token in _parse_pointer(pointer):
        current = _descend(current, token)
    return current


def _descend(container: object, token: str) -> object:
    """Traverse one existing object member or array index."""

    if isinstance(container, dict):
        if token not in container:
            raise _PatchError(f"object member not found: {token!r}")
        return container[token]
    if isinstance(container, list):
        index = _array_index(token, len(container), allow_end=False)
        return container[index]
    raise _PatchError(f"cannot traverse into {type(container).__name__}")


def _parent(document: object, tokens: list[str]) -> tuple[object, str]:
    """Resolve the parent container and final token for a non-root path."""

    if not tokens:
        raise _PatchError("root path has no parent")
    current = document
    for token in tokens[:-1]:
        current = _descend(current, token)
    return current, tokens[-1]


def _array_index(token: str, length: int, *, allow_end: bool) -> int:
    """Validate and parse one RFC array index."""

    if token == "-":
        if allow_end:
            return length
        raise _PatchError("array index '-' is only valid for add")
    if not token.isdecimal() or (len(token) > 1 and token.startswith("0")):
        raise _PatchError(f"invalid array index: {token!r}")
    try:
        index = int(token)
    except ValueError as exc:
        raise _PatchError(f"invalid array index: {token!r}") from exc
    limit = length if allow_end else length - 1
    if index > limit:
        raise _PatchError(f"array index out of bounds: {index}")
    return index


def _add(document: object, pointer: str, value: object) -> object:
    """Apply RFC 6902 add semantics."""

    tokens = _parse_pointer(pointer)
    cloned = _clone(value)
    if not tokens:
        return cloned
    parent, token = _parent(document, tokens)
    if isinstance(parent, dict):
        parent[token] = cloned
        return document
    if isinstance(parent, list):
        parent.insert(_array_index(token, len(parent), allow_end=True), cloned)
        return document
    raise _PatchError(f"add parent is not a container: {type(parent).__name__}")


def _remove(document: object, pointer: str) -> tuple[object, object]:
    """Apply RFC 6902 remove semantics and return the removed value."""

    tokens = _parse_pointer(pointer)
    if not tokens:
        return None, document
    parent, token = _parent(document, tokens)
    if isinstance(parent, dict):
        if token not in parent:
            raise _PatchError(f"object member not found: {token!r}")
        return document, parent.pop(token)
    if isinstance(parent, list):
        return document, parent.pop(_array_index(token, len(parent), allow_end=False))
    raise _PatchError(f"remove parent is not a container: {type(parent).__name__}")


def _replace(document: object, pointer: str, value: object) -> object:
    """Apply RFC 6902 replace semantics after existence validation."""

    tokens = _parse_pointer(pointer)
    cloned = _clone(value)
    if not tokens:
        return cloned
    parent, token = _parent(document, tokens)
    if isinstance(parent, dict):
        parent[token] = cloned
        return document
    if isinstance(parent, list):
        parent[_array_index(token, len(parent), allow_end=False)] = cloned
        return document
    raise _PatchError(f"replace parent is not a container: {type(parent).__name__}")


def _clone(value: object) -> object:
    """Deep-copy JSON data so copy/move operations cannot alias values."""

    try:
        return copy.deepcopy(value)
    except RecursionError as exc:
        raise _PatchError("JSON value exceeds supported nesting depth") from exc


def _json_equal(left: object, right: object) -> bool:
    """Compare JSON values using RFC 6902 structural equality."""

    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_json_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right, strict=True))
    return left == right
