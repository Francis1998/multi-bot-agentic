"""Typed, validated final outputs: a run-level JSON Schema contract for the final answer.

``run --output-schema schema.json`` makes the final answer of a run a JSON document that must
validate against a JSON Schema. This module holds the parts that never touch the event log or a
provider:

* :class:`OutputSchema`: a dependency-free validator for a documented JSON Schema subset. Every
  keyword of a schema is checked when it is loaded, so an unsupported keyword is an error instead
  of a constraint that is silently ignored. Schemas are bounded in size, nesting, and subschema
  count, ``$ref`` only points inside the schema, and nothing in a schema is executed or fetched.
* :func:`extract_json`: the deterministic rules that find the JSON document in a ``DONE:`` answer.
* :func:`check_output`: extraction, size bounds, and validation of one answer.
* :class:`OutputContract`: the schema plus the correction-round budget, as recorded in the first
  event of a run so ``resume`` and ``fork`` enforce the same contract.
* :func:`example_instance`: a schema-guided JSON document builder used by the fake provider.

Error paths name the offending value: ``$`` is the document, ``$.items[2].price`` a nested value.
Schema locations in schema errors are JSON pointers such as ``#/properties/price``.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

# Bounds on schemas: they are kept small enough to send to every provider call.
MAX_SCHEMA_BYTES: Final[int] = 65_536
MAX_SCHEMA_DEPTH: Final[int] = 32
MAX_SCHEMA_NODES: Final[int] = 2_000
# ``pattern`` limits (Python ``re`` has no timeout; see docs/SAFETY.md).
MAX_PATTERN_CHARS: Final[int] = 256
MAX_PATTERN_SUBJECT_CHARS: Final[int] = 4_096
# Provider output bound of runs with an output schema (other runs keep ModelRequest's 2,000).
MAX_ANSWER_CHARS: Final[int] = 16_000
# Bounds on the validated document recorded in the ``final_output`` event.
MAX_OUTPUT_BYTES: Final[int] = 65_536
MAX_OUTPUT_DEPTH: Final[int] = 64
# Validation errors kept per attempt (the rest are counted, not listed).
MAX_ERRORS: Final[int] = 20
DEFAULT_OUTPUT_RETRIES: Final[int] = 2
MAX_OUTPUT_RETRIES: Final[int] = 10
# Backstop for recursion through ``$ref``/``allOf``; cycles are already refused when loading.
_MAX_VALIDATION_DEPTH: Final[int] = 256
# Subschemas one value may be checked against through allOf/anyOf/oneOf/$ref (refused when loading),
# and the validation steps one answer may take (shared references can multiply the work).
MAX_SCHEMA_EXPANSION: Final[int] = 10_000
MAX_VALIDATION_STEPS: Final[int] = 500_000

JSON_TYPES: Final[tuple[str, ...]] = ("array", "boolean", "integer", "null", "number", "object", "string")
ANNOTATION_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"$schema", "$comment", "title", "description", "default", "examples", "deprecated", "readOnly", "writeOnly"}
)
DEFINITION_KEYWORDS: Final[frozenset[str]] = frozenset({"$defs", "definitions"})
ASSERTION_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "type",
        "enum",
        "const",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minLength",
        "maxLength",
        "pattern",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "anyOf",
        "oneOf",
        "allOf",
        "$ref",
    }
)
SUPPORTED_KEYWORDS: Final[frozenset[str]] = ANNOTATION_KEYWORDS | DEFINITION_KEYWORDS | ASSERTION_KEYWORDS
GUIDE: Final[str] = "docs/guides/STRUCTURED_OUTPUT_GUIDE.md"


class SchemaError(ValueError):
    """Raised when an output schema is invalid, unsupported, or too large. Nothing was run."""


class OutputExtractionError(ValueError):
    """Raised when no single JSON document can be read from a final answer."""


class _WorkLimitError(Exception):
    """Raised inside validation when an answer needs more than ``MAX_VALIDATION_STEPS`` steps."""


def strict_json_loads(text: str) -> Any:
    """Parse JSON text, refusing ``NaN``/``Infinity``, out-of-range numbers, and duplicate object keys.

    Python's ``json`` accepts all of them by default (``1e400`` becomes infinity); none can be
    recorded as JSON, and a duplicate key would make the recorded document differ from what the
    model wrote.

    Raises:
        ValueError: If the text is not strict JSON (``json.JSONDecodeError`` for syntax errors).
        RecursionError: If the document nests too deeply for the parser.
    """

    return json.loads(text, parse_constant=_refuse_constant, parse_float=_finite_float, object_pairs_hook=_unique_keys)


def _refuse_constant(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON")


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"the number {text[:40]} is out of range")
    return value


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key {json.dumps(key)}")
        result[key] = value
    return result


def canonical_json(value: Any) -> str:
    """Return compact JSON with sorted keys: the form that sizes and digests are computed on."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_of(value: Any) -> str:
    """Return the SHA-256 hex digest of :func:`canonical_json` of ``value``."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def json_type(value: Any) -> str:
    """Return the JSON type name of a decoded value (``integer`` for ints, ``number`` for floats)."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def json_key(value: Any) -> Any:
    """Return a hashable key under which equal JSON values (``1`` and ``1.0``, not ``true``) are equal."""

    if isinstance(value, bool):
        return ("boolean", value)
    if isinstance(value, (int, float)):
        return ("number", value)
    if isinstance(value, list):
        return ("array", tuple(json_key(item) for item in value))
    if isinstance(value, dict):
        return ("object", frozenset((key, json_key(item)) for key, item in value.items()))
    return (json_type(value), value)


def json_depth(value: Any) -> int:
    """Return the nesting depth of a decoded JSON value (``0`` for a scalar, ``1`` for ``[]``)."""

    depth = 0
    level: list[Any] = [value]
    while True:
        containers = [item for item in level if isinstance(item, (dict, list))]
        if not containers:
            return depth
        depth += 1
        level = [child for item in containers for child in (item.values() if isinstance(item, dict) else item)]


def preview(value: Any, limit: int = 60) -> str:
    """Return the compact JSON of ``value``, shortened to ``limit`` characters."""

    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def instance_path(path: str, key: str | int) -> str:
    """Append an object key or array index to an error path such as ``$.items[2]``."""

    if isinstance(key, int):
        return f"{path}[{key}]"
    if _IDENTIFIER.match(key):
        return f"{path}.{key}"
    return f"{path}[{json.dumps(key, ensure_ascii=False)}]"


def _pointer(path: str, token: str) -> str:
    """Append one escaped JSON-pointer token to a schema location such as ``#/properties``."""

    return f"{path}/{token.replace('~', '~0').replace('/', '~1')}"


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_BRACE_QUANTIFIER = re.compile(r"\{(\d+)(,(\d*))?\}")
_LOCAL_REF = re.compile(r"#(?:/(?:[^~/]|~[01])*)*")
# Longest error message kept (paths and previews come from model output).
_MAX_ERROR_CHARS: Final[int] = 300
# Schema files may be indented; the compact schema must still fit MAX_SCHEMA_BYTES.
MAX_SCHEMA_FILE_BYTES: Final[int] = 4 * MAX_SCHEMA_BYTES


def pattern_problem(pattern: str) -> str | None:
    """Return why a ``pattern`` is refused, or ``None`` when it may be used.

    Python's ``re`` engine backtracks and has no timeout, so patterns are bounded: at most
    :data:`MAX_PATTERN_CHARS` characters, no backreferences, and no repeated group whose content
    can vary in length (``(a+)+``, ``(a|ab)*``, ``(-[a-z]+)*``), the shape behind catastrophic
    backtracking. The check is conservative: it also refuses some safe patterns.

    Args:
        pattern: Regular expression from a schema.

    Returns:
        A reason such as ``"uses a backreference, which is not supported"``, or ``None``.
    """

    if len(pattern) > MAX_PATTERN_CHARS:
        return f"is {len(pattern)} characters long; the limit is {MAX_PATTERN_CHARS}"
    # One flag per open group (index 0 is the whole pattern): can its content vary in length?
    variable: list[bool] = [False]
    previous_group: bool | None = None
    index, length = 0, len(pattern)
    while index < length:
        char = pattern[index]
        closed: bool | None = None
        quantifier = _quantifier_at(pattern, index)
        if char == "\\":
            if index + 1 < length and pattern[index + 1] in "123456789":
                return "uses a backreference, which is not supported"
            index += 2
        elif char == "[":
            index = _class_end(pattern, index)
        elif char == "(":
            if pattern.startswith("(?P=", index):
                return "uses a backreference, which is not supported"
            variable.append(False)
            index += 2 if pattern.startswith("(?", index) else 1
        elif char == ")":
            if len(variable) > 1:
                closed = variable.pop()
                variable[-1] = variable[-1] or closed
            index += 1
        elif char == "|":
            variable[-1] = True
            index += 1
        elif quantifier is not None:
            end, repeats, varies = quantifier
            if repeats and previous_group:
                return (
                    "repeats a group whose content varies in length (such as (a+)+ or (a|ab)*), "
                    "which can backtrack catastrophically"
                )
            variable[-1] = variable[-1] or varies
            index = end + 1 if end < length and pattern[end] in "?+" else end
        else:
            index += 1
        previous_group = closed
    return None


def _quantifier_at(pattern: str, index: int) -> tuple[int, bool, bool] | None:
    """Return ``(end, repeats, varies)`` for a quantifier at ``index``, or ``None``."""

    char = pattern[index]
    if char in "*+":
        return index + 1, True, True
    if char == "?":
        return index + 1, False, True
    if char != "{":
        return None
    match = _BRACE_QUANTIFIER.match(pattern, index)
    if match is None:
        return None
    low = int(match.group(1) or 0)
    high = low if match.group(2) is None else (int(match.group(3)) if match.group(3) else None)
    return match.end(), high is None or high > 1, high != low


def _class_end(pattern: str, index: int) -> int:
    """Return the index just after the character class that starts at ``index``."""

    position = index + 1
    if pattern.startswith("^", position):
        position += 1
    if pattern.startswith("]", position):
        position += 1
    while position < len(pattern):
        if pattern[position] == "\\":
            position += 2
        elif pattern[position] == "]":
            return position + 1
        else:
            position += 1
    return len(pattern)


class _SchemaChecker:
    """One pass over a schema: checks every keyword and collects what validation needs."""

    def __init__(self, root: Any) -> None:
        self.root = root
        self.nodes = 0
        self.locations: set[str] = set()
        # Subschemas applied to the same value: allOf/anyOf/oneOf members and $ref targets.
        self.same_value: dict[str, list[str]] = {}
        self.refs: list[tuple[str, str]] = []
        self.patterns: dict[str, re.Pattern[str]] = {}

    def run(self) -> None:
        """Check the whole schema, its references, and refuse reference cycles."""

        self.walk(self.root, "#", 0)
        for location, target in self.refs:
            if target not in self.locations:
                raise SchemaError(
                    f"schema {location}: $ref {preview(target)} does not point to a schema in this document "
                    '(only local references such as "#/$defs/name" are supported)'
                )
            self.same_value.setdefault(location, []).append(target)
        self._refuse_cycles()
        self._refuse_expansion()

    def walk(self, schema: Any, location: str, depth: int) -> None:
        """Check one schema and everything under it."""

        if depth > MAX_SCHEMA_DEPTH:
            raise SchemaError(f"schema {location}: nesting exceeds {MAX_SCHEMA_DEPTH} levels")
        self.nodes += 1
        if self.nodes > MAX_SCHEMA_NODES:
            raise SchemaError(f"the schema has more than {MAX_SCHEMA_NODES} subschemas")
        self.locations.add(location)
        if isinstance(schema, bool):
            return
        if not isinstance(schema, dict):
            raise SchemaError(f"schema {location}: expected a schema object or a boolean, got {json_type(schema)}")
        unknown = sorted(keyword for keyword in schema if keyword not in SUPPORTED_KEYWORDS)
        if unknown:
            plural = "s" if len(unknown) > 1 else ""
            names = ", ".join(json.dumps(keyword) for keyword in unknown)
            raise SchemaError(
                f"schema {location}: unsupported keyword{plural} {names}; it would not be enforced, "
                f"so the schema is refused (supported keywords: {GUIDE})"
            )
        for keyword, value in schema.items():
            self._keyword(keyword, value, location, depth)

    def _keyword(self, keyword: str, value: Any, location: str, depth: int) -> None:
        """Check the value of one keyword."""

        at = _pointer(location, keyword)
        if keyword in DEFINITION_KEYWORDS or keyword == "properties":
            if not isinstance(value, dict):
                raise SchemaError(f"schema {at}: expected an object of schemas, got {json_type(value)}")
            for name, subschema in value.items():
                self.walk(subschema, _pointer(at, name), depth + 1)
        elif keyword in {"items", "additionalProperties"}:
            if keyword == "items" and isinstance(value, list):
                raise SchemaError(f"schema {at}: an array of schemas (tuple validation) is not supported")
            self.walk(value, at, depth + 1)
        elif keyword in {"anyOf", "oneOf", "allOf"}:
            if not isinstance(value, list) or not value:
                raise SchemaError(f"schema {at}: expected a non-empty array of schemas")
            for index, subschema in enumerate(value):
                member = _pointer(at, str(index))
                self.walk(subschema, member, depth + 1)
                self.same_value.setdefault(location, []).append(member)
        elif keyword == "$ref":
            if not isinstance(value, str) or not _LOCAL_REF.fullmatch(value):
                raise SchemaError(
                    f'schema {at}: only local references such as "#/$defs/name" are supported, got {preview(value)}'
                )
            self.refs.append((location, value))
        else:
            self._assertion(keyword, value, at)

    def _assertion(self, keyword: str, value: Any, at: str) -> None:
        """Check the value of a keyword that does not hold subschemas."""

        problem: str | None = None
        if keyword == "type":
            names = value if isinstance(value, list) else [value]
            if not names or len({str(name) for name in names}) != len(names) or any(n not in JSON_TYPES for n in names):
                problem = f"expected one of {', '.join(JSON_TYPES)}, or an array of them"
        elif keyword == "required":
            if not isinstance(value, list) or any(not isinstance(name, str) for name in value):
                problem = "expected an array of property names"
            elif len(set(value)) != len(value):
                problem = "property names must be unique"
        elif keyword == "enum":
            if not isinstance(value, list) or not value:
                problem = "expected a non-empty array"
        elif keyword in {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                problem = "expected a number"
        elif keyword in {"minLength", "maxLength", "minItems", "maxItems"}:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                problem = "expected a non-negative integer"
        elif keyword == "uniqueItems":
            if not isinstance(value, bool):
                problem = "expected true or false"
        elif keyword == "pattern":
            problem = self._pattern(value)
        if problem is not None:
            raise SchemaError(f"schema {at}: {problem}, got {preview(value)}")

    def _pattern(self, value: Any) -> str | None:
        """Compile a ``pattern`` once, or return why it is refused."""

        if not isinstance(value, str):
            return "expected a regular expression string"
        problem = pattern_problem(value)
        if problem is not None:
            return f"the pattern {problem}"
        try:
            self.patterns[value] = re.compile(value)
        except re.error as error:
            return f"invalid regular expression ({error})"
        return None

    def _refuse_cycles(self) -> None:
        """Refuse ``$ref``/``allOf`` chains that lead back to themselves without consuming the value."""

        done: set[str] = set()
        for start in sorted(self.same_value):
            if start in done:
                continue
            path = [start]
            stack = [iter(self.same_value.get(start, ()))]
            while stack:
                target = next(stack[-1], None)
                if target is None:
                    done.add(path.pop())
                    stack.pop()
                elif target in path:
                    cycle = " -> ".join([*path[path.index(target) :], target])
                    raise SchemaError(f"schema {target}: reference cycle {cycle} never reaches a property or item")
                elif target not in done:
                    path.append(target)
                    stack.append(iter(self.same_value.get(target, ())))

    def _refuse_expansion(self) -> None:
        """Refuse schemas whose shared references make one value be checked against too many subschemas.

        Each location's expansion counts itself plus, with multiplicity, everything its
        ``allOf``/``anyOf``/``oneOf`` members and ``$ref`` targets apply to the same value; a chain of
        definitions that each reference the previous one twice doubles it at every step.
        """

        sizes: dict[str, int] = {}
        for start in sorted(self.same_value):
            stack = [(start, False)]
            while stack:
                location, ready = stack.pop()
                if location in sizes:
                    continue
                targets = self.same_value.get(location, [])
                if not ready:
                    stack.append((location, True))
                    stack.extend((target, False) for target in targets if target not in sizes)
                    continue
                size = 1 + sum(sizes[target] for target in targets)
                if size > MAX_SCHEMA_EXPANSION:
                    raise SchemaError(
                        f"schema {location}: its allOf/anyOf/oneOf/$ref references expand to more than "
                        f"{MAX_SCHEMA_EXPANSION} subschemas for one value"
                    )
                sizes[location] = size


class _Validator:
    """Collects the errors of one value against a checked schema."""

    def __init__(self, root: Any, patterns: Mapping[str, re.Pattern[str]], budget: list[int] | None = None) -> None:
        self.root = root
        self.patterns = patterns
        self.errors: list[str] = []
        self.dropped = 0
        # Steps left for the whole answer, shared with the validators of anyOf/oneOf alternatives.
        self.budget = budget if budget is not None else [MAX_VALIDATION_STEPS]

    def add(self, path: str, message: str) -> None:
        if len(self.errors) >= MAX_ERRORS:
            self.dropped += 1
            return
        error = f"{path}: {message}"
        self.errors.append(error if len(error) <= _MAX_ERROR_CHARS else error[: _MAX_ERROR_CHARS - 1] + "…")

    def branch(self, schema: Any, value: Any, path: str, depth: int) -> list[str]:
        """Return the errors of ``value`` against one ``anyOf``/``oneOf`` alternative."""

        validator = _Validator(self.root, self.patterns, self.budget)
        validator.validate(schema, value, path, depth)
        return validator.errors

    def validate(self, schema: Any, value: Any, path: str, depth: int) -> None:
        self.budget[0] -= 1
        if self.budget[0] < 0:
            raise _WorkLimitError
        if depth > _MAX_VALIDATION_DEPTH:
            self.add(path, "the schema recursion limit was reached")
            return
        if schema is True:
            return
        if schema is False:
            self.add(path, "no value is allowed here (the schema is false)")
            return
        if "$ref" in schema:
            self.validate(self._resolve(schema["$ref"]), value, path, depth + 1)
        types = schema.get("type")
        if types is not None:
            names = types if isinstance(types, list) else [types]
            if not any(_has_type(value, name) for name in names):
                self.add(path, f"expected {' or '.join(names)}, got {json_type(value)}")
                return
        if "const" in schema and json_key(value) != json_key(schema["const"]):
            self.add(path, f"expected {preview(schema['const'])}, got {preview(value)}")
        if "enum" in schema and json_key(value) not in {json_key(item) for item in schema["enum"]}:
            self.add(path, f"expected one of {_choices(schema['enum'])}, got {preview(value)}")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            self._number(schema, value, path)
        elif isinstance(value, str):
            self._string(schema, value, path)
        elif isinstance(value, list):
            self._array(schema, value, path, depth)
        elif isinstance(value, dict):
            self._object(schema, value, path, depth)
        for member in schema.get("allOf", ()):
            self.validate(member, value, path, depth + 1)
        if "anyOf" in schema:
            results = [self.branch(member, value, path, depth + 1) for member in schema["anyOf"]]
            if all(results):
                self.add(path, f"does not match any of the {len(results)} anyOf alternatives{_closest(results)}")
        if "oneOf" in schema:
            results = [self.branch(member, value, path, depth + 1) for member in schema["oneOf"]]
            matched = [str(index) for index, errors in enumerate(results) if not errors]
            if not matched:
                self.add(path, f"does not match any of the {len(results)} oneOf alternatives{_closest(results)}")
            elif len(matched) > 1:
                self.add(
                    path, f"matches {len(matched)} oneOf alternatives ({', '.join(matched)}); expected exactly one"
                )

    def _resolve(self, ref: str) -> Any:
        target = self.root
        for token in ref[2:].split("/") if ref != "#" else ():
            name = token.replace("~1", "/").replace("~0", "~")
            target = target[int(name)] if isinstance(target, list) else target[name]
        return target

    def _number(self, schema: Mapping[str, Any], value: float, path: str) -> None:
        for keyword, operator in (
            ("minimum", ">="),
            ("exclusiveMinimum", ">"),
            ("maximum", "<="),
            ("exclusiveMaximum", "<"),
        ):
            limit = schema.get(keyword)
            if limit is None:
                continue
            within = {
                ">=": value >= limit,
                ">": value > limit,
                "<=": value <= limit,
                "<": value < limit,
            }[operator]
            if not within:
                self.add(path, f"expected a number {operator} {json.dumps(limit)}, got {json.dumps(value)}")

    def _string(self, schema: Mapping[str, Any], value: str, path: str) -> None:
        length = len(value)
        if "minLength" in schema and length < schema["minLength"]:
            self.add(path, f"expected at least {_plural(schema['minLength'], 'character')}, got {length}")
        if "maxLength" in schema and length > schema["maxLength"]:
            self.add(path, f"expected at most {_plural(schema['maxLength'], 'character')}, got {length}")
        pattern = schema.get("pattern")
        if pattern is None:
            return
        if length > MAX_PATTERN_SUBJECT_CHARS:
            self.add(
                path,
                f"is {length} characters long, too long to check against pattern {preview(pattern)} "
                f"(limit {MAX_PATTERN_SUBJECT_CHARS})",
            )
        elif self.patterns[pattern].search(value) is None:
            self.add(path, f"does not match pattern {preview(pattern)}")

    def _array(self, schema: Mapping[str, Any], value: list[Any], path: str, depth: int) -> None:
        count = len(value)
        if "minItems" in schema and count < schema["minItems"]:
            self.add(path, f"expected at least {_plural(schema['minItems'], 'item')}, got {count}")
        if "maxItems" in schema and count > schema["maxItems"]:
            self.add(path, f"expected at most {_plural(schema['maxItems'], 'item')}, got {count}")
        if schema.get("uniqueItems") is True:
            seen: dict[Any, int] = {}
            for index, item in enumerate(value):
                key = json_key(item)
                if key in seen:
                    self.add(path, f"items must be unique, but items {seen[key]} and {index} are equal")
                    break
                seen[key] = index
        items = schema.get("items")
        if items is not None:
            for index, item in enumerate(value):
                self.validate(items, item, instance_path(path, index), depth + 1)

    def _object(self, schema: Mapping[str, Any], value: dict[str, Any], path: str, depth: int) -> None:
        properties: Mapping[str, Any] = schema.get("properties", {})
        for name in schema.get("required", ()):
            if name not in value:
                self.add(instance_path(path, name), "required property is missing")
        extra = schema.get("additionalProperties", True)
        for name, item in value.items():
            if name in properties:
                self.validate(properties[name], item, instance_path(path, name), depth + 1)
            elif extra is False:
                self.add(instance_path(path, name), f"additional property is not allowed{_allowed(properties)}")
            else:
                self.validate(extra, item, instance_path(path, name), depth + 1)


def _has_type(value: Any, name: str) -> bool:
    """Return whether ``value`` has JSON type ``name`` (``1.0`` is an integer, ``true`` is not a number)."""

    if name == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (
            isinstance(value, float) and value.is_integer()
        )
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return json_type(value) == name


def _choices(values: Sequence[Any]) -> str:
    shown = ", ".join(preview(item, 40) for item in values[:8])
    return f"[{shown}{', …' if len(values) > 8 else ''}]"


def _closest(results: Sequence[Sequence[str]]) -> str:
    index = min(range(len(results)), key=lambda position: (len(results[position]), position))
    return f"; closest is alternative {index}: {results[index][0]}" if results[index] else ""


def _allowed(properties: Mapping[str, Any]) -> str:
    names = list(properties)
    if not names:
        return ""
    shown = ", ".join(names[:10])
    return f" (allowed: {shown}{', …' if len(names) > 10 else ''})"


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


@dataclass(frozen=True)
class OutputSchema:
    """A checked output schema.

    Attributes:
        value: The schema (an object or a boolean).
        sha256: SHA-256 of its compact JSON (:func:`sha256_of`); identifies the contract in events.
        source: Where it was loaded from (a file path), if known.
        patterns: Compiled ``pattern`` regular expressions.
    """

    value: Any
    sha256: str
    source: str | None = None
    patterns: Mapping[str, re.Pattern[str]] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_value(cls, value: Any, *, source: str | None = None) -> OutputSchema:
        """Check a decoded schema.

        Raises:
            SchemaError: If the schema is too large, malformed, or uses an unsupported keyword.
        """

        try:
            text = canonical_json(value)
            size = len(text.encode("utf-8"))
        except (TypeError, ValueError) as error:
            raise SchemaError(f"the output schema is not JSON: {error}") from error
        if size > MAX_SCHEMA_BYTES:
            raise SchemaError(f"the output schema is {size} bytes in compact form; the limit is {MAX_SCHEMA_BYTES}")
        checker = _SchemaChecker(value)
        checker.run()
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return cls(value=value, sha256=digest, source=source, patterns=dict(checker.patterns))

    @classmethod
    def load(cls, path: Path) -> OutputSchema:
        """Read and check a schema file (strict JSON, at most :data:`MAX_SCHEMA_FILE_BYTES`).

        Raises:
            SchemaError: If the file cannot be read, is not strict JSON, or the schema is refused.
        """

        try:
            size = path.stat().st_size
            if size > MAX_SCHEMA_FILE_BYTES:
                raise SchemaError(f"output schema {path} is {size} bytes; the limit is {MAX_SCHEMA_FILE_BYTES}")
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise SchemaError(f"cannot read output schema {path}: {error.strerror or error}") from error
        except UnicodeDecodeError as error:
            raise SchemaError(f"output schema {path} is not UTF-8 text: {error}") from error
        try:
            value = strict_json_loads(text)
        except RecursionError:
            raise SchemaError(f"output schema {path} nests too deeply") from None
        except ValueError as error:
            raise SchemaError(f"output schema {path} is not valid JSON: {error}") from error
        try:
            return cls.from_value(value, source=str(path))
        except SchemaError as error:
            raise SchemaError(f"output schema {path}: {error}") from error

    def validate(self, value: Any) -> tuple[str, ...]:
        """Return the validation errors of a decoded JSON value (empty when it is valid)."""

        validator = _Validator(self.value, self.patterns)
        try:
            validator.validate(self.value, value, "$", 0)
        except _WorkLimitError:
            return (
                f"$: validation stopped after {MAX_VALIDATION_STEPS} steps: the schema's references multiply "
                "the work for this value; simplify the schema",
            )
        if validator.dropped:
            validator.errors.append(f"({_plural(validator.dropped, 'more error')} not shown)")
        return tuple(validator.errors)


def extract_json(answer: str) -> tuple[Any, str]:
    """Read the one JSON document in a final answer (the text after ``DONE:``).

    Rules, applied in order:

    1. The whole answer, without surrounding whitespace, is a JSON document: it is the output
       (source ``answer``).
    2. Otherwise exactly one fenced block whose info string is ``json`` (```` ```json ````, any case,
       fences on their own lines) holds the output (source ``json_block``). Two or more such blocks
       are an error, never a guess.
    3. Otherwise there is no output. An answer that starts as JSON but is not valid (a syntax error
       after its first character, an out-of-range number, ``NaN``, a duplicate key) reports that
       error; any other answer reports that no JSON document was found.

    JSON is parsed strictly (:func:`strict_json_loads`).

    Args:
        answer: Final answer text.

    Returns:
        The decoded document and its source.

    Raises:
        OutputExtractionError: If no single JSON document can be read.
    """

    text = answer.strip()
    if not text:
        raise OutputExtractionError("the final answer is empty")
    try:
        return strict_json_loads(text), "answer"
    except RecursionError:
        raise OutputExtractionError("the JSON document nests too deeply to parse") from None
    except ValueError as error:
        whole_error = str(error)
        # A syntax error at the first character means the answer is not JSON at all.
        starts_as_json = not isinstance(error, json.JSONDecodeError) or error.pos > 0
    blocks = _json_blocks(text)
    if len(blocks) > 1:
        raise OutputExtractionError(f"the answer has {len(blocks)} ```json blocks; return exactly one JSON document")
    if blocks:
        body, closed = blocks[0]
        if not closed:
            raise OutputExtractionError("the ```json block is not closed by a ``` line")
        try:
            return strict_json_loads(body), "json_block"
        except RecursionError:
            raise OutputExtractionError("the JSON document nests too deeply to parse") from None
        except ValueError as error:
            raise OutputExtractionError(f"the ```json block is not valid JSON: {error}") from None
    if starts_as_json:
        raise OutputExtractionError(f"the answer is not valid JSON: {whole_error}")
    raise OutputExtractionError(
        "no JSON document found; reply with only the JSON document, or put it in one ```json fenced block"
    )


def _json_blocks(text: str) -> list[tuple[str, bool]]:
    """Return the body of every ```` ```json ```` fenced block and whether it was closed."""

    blocks: list[tuple[str, bool]] = []
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        opening = lines[index].strip()
        index += 1
        if not opening.startswith("```"):
            continue
        info = opening[3:].strip().lower()
        body: list[str] = []
        closed = False
        while index < len(lines):
            line = lines[index]
            index += 1
            if line.strip() == "```":
                closed = True
                break
            body.append(line)
        if info == "json":
            blocks.append(("\n".join(body), closed))
    return blocks


@dataclass(frozen=True)
class OutputCheck:
    """Outcome of checking one final answer against an output schema.

    Attributes:
        errors: Validation errors with their paths; empty when the answer is valid.
        value: The extracted JSON document, when one was found (it may itself be ``null``).
        found: True when a JSON document within the size bounds was extracted.
        source: ``answer`` (the whole answer) or ``json_block`` (one fenced block), when found.
        output_bytes: Size of the document's compact JSON.
    """

    errors: tuple[str, ...]
    value: Any = None
    found: bool = False
    source: str | None = None
    output_bytes: int = 0

    @property
    def valid(self) -> bool:
        """Return whether a document was found and it validates."""

        return self.found and not self.errors


def check_output(answer: str, schema: OutputSchema) -> OutputCheck:
    """Extract the JSON document from a final answer, bound its size and depth, and validate it.

    Args:
        answer: Final answer text.
        schema: Output schema.

    Returns:
        The check; never raises for any answer text.
    """

    try:
        value, source = extract_json(answer)
    except OutputExtractionError as error:
        return OutputCheck(errors=(f"$: {error}",))
    if json_depth(value) > MAX_OUTPUT_DEPTH:
        return OutputCheck(errors=(f"$: the JSON document nests deeper than {MAX_OUTPUT_DEPTH} levels",), source=source)
    try:
        size = len(canonical_json(value).encode("utf-8"))
    except UnicodeEncodeError:
        return OutputCheck(
            errors=("$: the JSON document is not valid Unicode (it has an unpaired \\uD800-\\uDFFF escape)",),
            source=source,
        )
    if size > MAX_OUTPUT_BYTES:
        return OutputCheck(
            errors=(f"$: the JSON document is {size} bytes in compact form; the limit is {MAX_OUTPUT_BYTES}",),
            source=source,
            output_bytes=size,
        )
    return OutputCheck(errors=schema.validate(value), value=value, found=True, source=source, output_bytes=size)


# Key of the contract in a run's first event (``run_created``, or ``run_forked`` for a fork).
CONTRACT_KEY: Final[str] = "output_contract"
# Source of the observation that feeds validation errors back to the model.
CORRECTION_SOURCE: Final[str] = "output:validation"
OUTPUT_VALIDATION_FAILED: Final[str] = "output_validation_failed"
FINAL_OUTPUT: Final[str] = "final_output"


@dataclass(frozen=True)
class OutputContract:
    """The output contract of a run: its schema and how many correction rounds it allows.

    Attributes:
        schema: Output schema.
        retries: Correction rounds after the first invalid answer (``--output-retries``).
    """

    schema: OutputSchema
    retries: int = DEFAULT_OUTPUT_RETRIES

    def __post_init__(self) -> None:
        if isinstance(self.retries, bool) or not isinstance(self.retries, int):
            raise ValueError(f"output retries must be an integer, got {self.retries!r}")
        if not 0 <= self.retries <= MAX_OUTPUT_RETRIES:
            raise ValueError(f"output retries must be between 0 and {MAX_OUTPUT_RETRIES}, got {self.retries}")

    @property
    def max_attempts(self) -> int:
        """Return the answers that may be checked: the first one plus one per correction round."""

        return self.retries + 1

    def summary(self) -> dict[str, Any]:
        """Return the contract without the schema body (for lineage, dry runs, and reports)."""

        return {"schema_sha256": self.schema.sha256, "source": self.schema.source, "retries": self.retries}

    def to_payload(self) -> dict[str, Any]:
        """Return the contract as recorded in a run's first event, schema included."""

        return {"schema": self.schema.value, **self.summary()}

    @classmethod
    def from_payload(cls, payload: Any) -> OutputContract:
        """Rebuild a recorded contract; the schema is checked again and must match its digest.

        Raises:
            SchemaError: If the recorded contract is malformed or its schema changed.
        """

        if not isinstance(payload, dict) or "schema" not in payload:
            raise SchemaError("the recorded output contract is malformed")
        source = payload.get("source")
        schema = OutputSchema.from_value(payload["schema"], source=source if isinstance(source, str) else None)
        if schema.sha256 != payload.get("schema_sha256"):
            raise SchemaError("the recorded output schema does not match its sha256 digest")
        try:
            return cls(schema=schema, retries=payload.get("retries", DEFAULT_OUTPUT_RETRIES))
        except ValueError as error:
            raise SchemaError(f"the recorded output contract is malformed: {error}") from error


@dataclass(frozen=True)
class FinalOutput:
    """A validated final output, as recorded in a ``final_output`` event.

    Attributes:
        value: The JSON document.
        attempt: Which answer of the run validated (``1`` is the first).
        source: ``answer`` or ``json_block`` (see :func:`extract_json`).
        output_sha256: SHA-256 of the document's compact JSON.
        output_bytes: Size of the document's compact JSON.
        schema_sha256: Digest of the schema it validated against.
    """

    value: Any
    attempt: int
    source: str
    output_sha256: str
    output_bytes: int
    schema_sha256: str

    def to_payload(self) -> dict[str, Any]:
        """Return the ``final_output`` event payload."""

        return {
            "output": self.value,
            "attempt": self.attempt,
            "source": self.source,
            "output_sha256": self.output_sha256,
            "bytes": self.output_bytes,
            "schema_sha256": self.schema_sha256,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> FinalOutput:
        """Rebuild a recorded final output (missing fields get neutral defaults)."""

        attempt = payload.get("attempt")
        size = payload.get("bytes")
        return cls(
            value=payload.get("output"),
            attempt=attempt if isinstance(attempt, int) and not isinstance(attempt, bool) else 0,
            source=str(payload.get("source") or "answer"),
            output_sha256=str(payload.get("output_sha256") or ""),
            output_bytes=size if isinstance(size, int) and not isinstance(size, bool) else 0,
            schema_sha256=str(payload.get("schema_sha256") or ""),
        )


def recorded_contract(events: Sequence[Any]) -> OutputContract | None:
    """Return the output contract a run recorded in its first event, or ``None``.

    The first event of an original run is ``run_created``; a fork's is ``run_forked``, which
    always carries the fork's own contract (inherited or overridden).

    Args:
        events: Event records of one run (``EventRecord``).

    Raises:
        SchemaError: If the recorded contract is malformed.
    """

    if not events:
        return None
    first = min(events, key=lambda event: event.seq)
    if first.event_type not in {"run_created", "run_forked"}:
        return None
    payload = first.payload.get(CONTRACT_KEY)
    return None if payload is None else OutputContract.from_payload(payload)


def failed_attempts(events: Sequence[Any], schema_sha256: str) -> int:
    """Count the ``output_validation_failed`` events of a run under the schema with this digest."""

    return sum(
        1
        for event in events
        if event.event_type == OUTPUT_VALIDATION_FAILED and event.payload.get("schema_sha256") == schema_sha256
    )


def recorded_output(events: Sequence[Any]) -> tuple[FinalOutput | None, tuple[str, ...]]:
    """Return a run's latest ``final_output`` and the errors of its latest failed attempt."""

    output: FinalOutput | None = None
    errors: tuple[str, ...] = ()
    for event in sorted(events, key=lambda item: item.seq):
        if event.event_type == FINAL_OUTPUT:
            output = FinalOutput.from_payload(event.payload)
        elif event.event_type == OUTPUT_VALIDATION_FAILED:
            raw = event.payload.get("errors")
            errors = tuple(str(item) for item in raw) if isinstance(raw, list) else ()
    return output, errors


def correction_text(errors: Sequence[str], *, attempt: int, contract: OutputContract) -> str:
    """Return the observation text that asks the model to correct an invalid final answer.

    It lists the validation errors, never the schema again: the schema is already part of every
    model request of the run.
    """

    lines = [
        f"OUTPUT_INVALID: final answer attempt {attempt} of {contract.max_attempts} failed validation "
        f"against the output schema (sha256 {contract.schema.sha256[:12]}):"
    ]
    lines.extend(f"- {error}" for error in errors)
    lines.append("Reply with DONE: followed by only the corrected JSON document.")
    return "\n".join(lines)


def example_instance(schema: OutputSchema, *, text: str, items: Sequence[str] = ()) -> Any:
    """Build a JSON document shaped by a schema, filled in from ``text`` and ``items``.

    The fake provider answers a correction round with it. It follows ``type``, ``enum``,
    ``const``, ``properties``/``required``, ``items``, length and count bounds, numeric bounds,
    ``$ref``, and the first ``anyOf``/``oneOf``/``allOf`` member; it does not try to satisfy
    ``pattern``, so the document can still be invalid for elaborate schemas.

    Args:
        schema: Output schema.
        text: Text for string values (the fake uses the goal).
        items: Strings for arrays (the fake uses the lines of the latest tool result).

    Returns:
        A JSON-serializable value.
    """

    return _Example(schema.value, text.strip() or "output", tuple(item for item in items if item.strip())).build(
        schema.value, None, 0
    )


@dataclass(frozen=True)
class _Example:
    root: Any
    text: str
    items: tuple[str, ...]

    def build(self, schema: Any, seed: str | None, depth: int) -> Any:
        if not isinstance(schema, dict) or depth > MAX_SCHEMA_DEPTH:
            return seed or self.text
        if "$ref" in schema:
            target = _Validator(self.root, {})._resolve(schema["$ref"])
            rest = {key: value for key, value in schema.items() if key != "$ref"}
            return self.build({**target, **rest} if isinstance(target, dict) else target, seed, depth + 1)
        if "const" in schema:
            return schema["const"]
        if "enum" in schema:
            return schema["enum"][0]
        for keyword in ("allOf", "anyOf", "oneOf"):
            if keyword in schema:
                first = schema[keyword][0]
                rest = {key: value for key, value in schema.items() if key != keyword}
                return self.build({**rest, **first} if isinstance(first, dict) else rest, seed, depth + 1)
        kind = _kind(schema)
        if kind == "object":
            properties: Mapping[str, Any] = schema.get("properties", {})
            document = {name: self.build(subschema, None, depth + 1) for name, subschema in properties.items()}
            for name in schema.get("required", ()):
                document.setdefault(name, self.text)
            return document
        if kind == "array":
            low, high = schema.get("minItems", 0), schema.get("maxItems")
            count = max(low, len(self.items) or 1)
            count = count if high is None else min(count, high)
            seeds = [
                self.items[index] if index < len(self.items) else f"{self.text} {index + 1}" for index in range(count)
            ]
            return [self.build(schema.get("items", {}), item, depth + 1) for item in seeds]
        if kind in {"integer", "number"}:
            return _bounded_number(schema, kind, default=len(self.items) or 1)
        if kind == "boolean":
            return True
        if kind == "null":
            return None
        value = seed or self.text
        value = value[: schema["maxLength"]] if "maxLength" in schema else value
        return value.ljust(schema.get("minLength", 0), ".")


def _kind(schema: Mapping[str, Any]) -> str:
    """Return the type a schema most likely wants (its first non-null ``type``, or a guess)."""

    declared = schema.get("type")
    names = declared if isinstance(declared, list) else [declared] if isinstance(declared, str) else []
    for name in names:
        if name != "null":
            return str(name)
    if names:
        return "null"
    if {"properties", "required", "additionalProperties"} & schema.keys():
        return "object"
    if {"items", "minItems", "maxItems", "uniqueItems"} & schema.keys():
        return "array"
    if {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"} & schema.keys():
        return "number"
    return "string"


def _bounded_number(schema: Mapping[str, Any], kind: str, *, default: int) -> int | float:
    """Return ``default`` moved inside the schema's numeric bounds."""

    value: float = default
    if "minimum" in schema:
        value = max(value, schema["minimum"])
    if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
        value = schema["exclusiveMinimum"] + 1
    if "maximum" in schema:
        value = min(value, schema["maximum"])
    if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
        value = schema["exclusiveMaximum"] - 1
    if kind == "integer":
        return int(value) if float(value).is_integer() else int(value) + 1
    return value


def write_output_file(path: Path, value: Any) -> None:
    """Write a validated output as indented JSON with sorted keys, atomically.

    The document is written to a temporary file next to ``path`` and renamed over it, so readers
    never see a partial file.

    Raises:
        OSError: If the file cannot be written.
    """

    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
