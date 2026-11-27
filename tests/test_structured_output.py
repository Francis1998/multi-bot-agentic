"""Unit tests for the output-schema validator, answer extraction, and output contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from multi_bot_agentic.structured_output import (
    MAX_OUTPUT_BYTES,
    MAX_PATTERN_SUBJECT_CHARS,
    MAX_SCHEMA_BYTES,
    MAX_SCHEMA_DEPTH,
    MAX_SCHEMA_NODES,
    OutputContract,
    OutputExtractionError,
    OutputSchema,
    SchemaError,
    check_output,
    example_instance,
    extract_json,
    pattern_problem,
    write_output_file,
)


def _errors(schema: Any, value: Any) -> tuple[str, ...]:
    return OutputSchema.from_value(schema).validate(value)


KEYWORD_CASES: list[tuple[str, Any, Any, tuple[str, ...]]] = [
    ("type", {"type": "string"}, "ok", ()),
    ("type", {"type": "object"}, [], ("$: expected object, got array",)),
    ("type-list", {"type": ["string", "null"]}, None, ()),
    ("type-list", {"type": ["string", "null"]}, 3, ("$: expected string or null, got integer",)),
    ("integer-float", {"type": "integer"}, 2.0, ()),
    ("integer", {"type": "integer"}, 2.5, ("$: expected integer, got number",)),
    ("boolean-is-not-number", {"type": "number"}, True, ("$: expected number, got boolean",)),
    ("enum", {"enum": ["low", "high"]}, "high", ()),
    ("enum", {"enum": ["low", "high"]}, "urgent", ('$: expected one of ["low", "high"], got "urgent"',)),
    ("enum-number-equality", {"enum": [1]}, 1.0, ()),
    ("enum-bool-is-not-1", {"enum": [1]}, True, ("$: expected one of [1], got true",)),
    ("const", {"const": {"a": [1, 2]}}, {"a": [1, 2]}, ()),
    ("const", {"const": 3}, 4, ("$: expected 3, got 4",)),
    ("minimum", {"minimum": 1}, 0, ("$: expected a number >= 1, got 0",)),
    ("maximum", {"maximum": 1}, 1.5, ("$: expected a number <= 1, got 1.5",)),
    ("exclusiveMinimum", {"exclusiveMinimum": 0}, 0, ("$: expected a number > 0, got 0",)),
    ("exclusiveMaximum", {"exclusiveMaximum": 10}, 10, ("$: expected a number < 10, got 10",)),
    ("minLength", {"minLength": 3}, "ab", ("$: expected at least 3 characters, got 2",)),
    ("maxLength", {"maxLength": 1}, "ab", ("$: expected at most 1 character, got 2",)),
    ("pattern", {"pattern": "^[A-Z]{3}$"}, "ABC", ()),
    ("pattern", {"pattern": "^[A-Z]{3}$"}, "abc", ('$: does not match pattern "^[A-Z]{3}$"',)),
    ("pattern-is-a-search", {"pattern": "[0-9]"}, "a1b", ()),
    ("minItems", {"minItems": 2}, [1], ("$: expected at least 2 items, got 1",)),
    ("maxItems", {"maxItems": 1}, [1, 2], ("$: expected at most 1 item, got 2",)),
    ("uniqueItems", {"uniqueItems": True}, [1, 2, 1.0], ("$: items must be unique, but items 0 and 2 are equal",)),
    (
        "uniqueItems-objects",
        {"uniqueItems": True},
        [{"a": 1, "b": 2}, {"b": 2, "a": 1}],
        ("$: items must be unique, but items 0 and 1 are equal",),
    ),
    ("items", {"items": {"type": "number"}}, [1, "x"], ("$[1]: expected number, got string",)),
    ("required", {"required": ["title"]}, {}, ("$.title: required property is missing",)),
    ("properties", {"properties": {"a": {"type": "string"}}}, {"a": 1}, ("$.a: expected string, got integer",)),
    (
        "additionalProperties-false",
        {"properties": {"a": {}}, "additionalProperties": False},
        {"a": 1, "b": 2},
        ("$.b: additional property is not allowed (allowed: a)",),
    ),
    (
        "additionalProperties-schema",
        {"additionalProperties": {"type": "integer"}},
        {"x": "1"},
        ("$.x: expected integer, got string",),
    ),
    ("anyOf", {"anyOf": [{"type": "string"}, {"type": "integer"}]}, 3, ()),
    (
        "anyOf",
        {"anyOf": [{"type": "string"}, {"type": "integer"}]},
        2.5,
        (
            "$: does not match any of the 2 anyOf alternatives; "
            "closest is alternative 0: $: expected string, got number",
        ),
    ),
    ("oneOf", {"oneOf": [{"type": "string"}, {"minLength": 5}]}, "abc", ()),
    (
        "oneOf-two-match",
        {"oneOf": [{"type": "string"}, {"minLength": 2}]},
        "abc",
        ("$: matches 2 oneOf alternatives (0, 1); expected exactly one",),
    ),
    ("allOf", {"allOf": [{"minimum": 1}, {"maximum": 3}]}, 5, ("$: expected a number <= 3, got 5",)),
    (
        "ref",
        {"$defs": {"price": {"type": "number"}}, "$ref": "#/$defs/price"},
        "free",
        ("$: expected number, got string",),
    ),
    (
        "definitions-ref",
        {"definitions": {"n": {"minimum": 0}}, "items": {"$ref": "#/definitions/n"}},
        [-1],
        ("$[0]: expected a number >= 0, got -1",),
    ),
    ("false-schema", {"properties": {"x": False}}, {"x": 1}, ("$.x: no value is allowed here (the schema is false)",)),
    ("true-schema", True, {"anything": [1]}, ()),
    ("annotations", {"title": "T", "description": "d", "default": 1, "examples": [1], "$comment": "c"}, 1, ()),
]


@pytest.mark.parametrize(
    ("schema", "value", "expected"), [case[1:] for case in KEYWORD_CASES], ids=[case[0] for case in KEYWORD_CASES]
)
def test_keyword(schema: Any, value: Any, expected: tuple[str, ...]) -> None:
    assert _errors(schema, value) == expected


def test_error_paths_name_the_offending_value() -> None:
    schema = {
        "type": "object",
        "properties": {
            "items": {"type": "array", "items": {"$ref": "#/$defs/item"}},
            "odd key": {"type": "string"},
        },
        "$defs": {"item": {"type": "object", "required": ["price"], "properties": {"price": {"type": "number"}}}},
    }
    errors = _errors(schema, {"items": [{"price": 1}, {"price": 2}, {"price": "3"}, {}], "odd key": 1})
    assert errors == (
        "$.items[2].price: expected number, got string",
        "$.items[3].price: required property is missing",
        '$["odd key"]: expected string, got integer',
    )


def test_recursive_schemas_are_allowed() -> None:
    tree = {"type": "object", "properties": {"children": {"type": "array", "items": {"$ref": "#"}}}}
    assert _errors(tree, {"children": [{"children": []}, {"children": [{"children": "x"}]}]}) == (
        "$.children[1].children[0].children: expected array, got string",
    )


def test_errors_are_capped_and_counted() -> None:
    errors = _errors({"items": {"type": "string"}}, list(range(25)))
    assert len(errors) == 21
    assert errors[-1] == "(5 more errors not shown)"


@pytest.mark.parametrize(
    ("schema", "message"),
    [
        ({"format": "date"}, 'schema #: unsupported keyword "format"; it would not be enforced'),
        ({"properties": {"a": {"not": {}}}}, 'schema #/properties/a: unsupported keyword "not"'),
        ({"$id": "x", "if": {}}, 'unsupported keywords "$id", "if"'),
        ({"items": [{}]}, "schema #/items: an array of schemas (tuple validation) is not supported"),
        ({"$ref": "https://example.com/s.json"}, 'only local references such as "#/$defs/name" are supported'),
        ({"$ref": "#/$defs/missing"}, "does not point to a schema in this document"),
        ({"required": ["a", "a"]}, "schema #/required: property names must be unique"),
        ({"type": "str"}, "schema #/type: expected one of array, boolean, integer"),
        ({"minLength": -1}, "schema #/minLength: expected a non-negative integer"),
        ({"exclusiveMinimum": True}, "schema #/exclusiveMinimum: expected a number"),
        ({"enum": []}, "schema #/enum: expected a non-empty array"),
        ({"anyOf": []}, "schema #/anyOf: expected a non-empty array of schemas"),
        ({"pattern": "("}, "schema #/pattern: invalid regular expression"),
        ({"properties": []}, "schema #/properties: expected an object of schemas"),
        ([], "schema #: expected a schema object or a boolean, got array"),
        (
            {"$defs": {"a": {"$ref": "#/$defs/b"}, "b": {"allOf": [{"$ref": "#/$defs/a"}]}}},
            "reference cycle #/$defs/a -> #/$defs/b -> #/$defs/b/allOf/0 -> #/$defs/a never reaches",
        ),
    ],
)
def test_invalid_or_unsupported_schemas_are_refused(schema: Any, message: str) -> None:
    with pytest.raises(SchemaError) as raised:
        OutputSchema.from_value(schema)
    assert message in str(raised.value)


def test_schema_limits() -> None:
    nested: dict[str, Any] = {}
    for _ in range(MAX_SCHEMA_DEPTH + 1):
        nested = {"items": nested}
    with pytest.raises(SchemaError, match=f"nesting exceeds {MAX_SCHEMA_DEPTH} levels"):
        OutputSchema.from_value(nested)
    wide: dict[str, Any] = {"properties": {f"p{index}": {} for index in range(MAX_SCHEMA_NODES)}}
    with pytest.raises(SchemaError, match=f"more than {MAX_SCHEMA_NODES} subschemas"):
        OutputSchema.from_value(wide)
    big = {"description": "x" * MAX_SCHEMA_BYTES}
    with pytest.raises(SchemaError, match=f"the limit is {MAX_SCHEMA_BYTES}"):
        OutputSchema.from_value(big)


@pytest.mark.parametrize(
    ("pattern", "refused"),
    [
        ("^[A-Z]{3}-\\d{4}$", None),
        ("(\\d{3}-)+", None),
        ("(ab)?c", None),
        ("[(+*]+", None),
        ("\\(a+\\)+", None),
        ("(a+)+$", "repeats a group whose content varies"),
        ("(a|ab)*", "repeats a group whose content varies"),
        ("((a)+){2}", "repeats a group whose content varies"),
        ("(?:x*y)+", "repeats a group whose content varies"),
        ("(a)\\1", "backreference"),
        ("(?P<n>a)(?P=n)", "backreference"),
        ("a" * 257, "the limit is 256"),
    ],
)
def test_pattern_problem(pattern: str, refused: str | None) -> None:
    problem = pattern_problem(pattern)
    if refused is None:
        assert problem is None
    else:
        assert problem is not None and refused in problem


def test_pattern_subject_is_bounded() -> None:
    long_text = "a" * (MAX_PATTERN_SUBJECT_CHARS + 1)
    assert _errors({"pattern": "a"}, long_text) == (
        f'$: is {MAX_PATTERN_SUBJECT_CHARS + 1} characters long, too long to check against pattern "a" '
        f"(limit {MAX_PATTERN_SUBJECT_CHARS})",
    )


def test_load_reads_strict_json_files(tmp_path: Path) -> None:
    path = tmp_path / "schema.json"
    path.write_text('{"type": "object", "type": "array"}', encoding="utf-8")
    with pytest.raises(SchemaError, match='is not valid JSON: duplicate object key "type"'):
        OutputSchema.load(path)
    path.write_text(json.dumps({"type": "string"}, indent=2), encoding="utf-8")
    schema = OutputSchema.load(path)
    assert schema.source == str(path) and len(schema.sha256) == 64
    with pytest.raises(SchemaError, match="cannot read output schema"):
        OutputSchema.load(tmp_path / "missing.json")


@pytest.mark.parametrize(
    ("answer", "value", "source"),
    [
        ('{"a": 1}', {"a": 1}, "answer"),
        ("  [1, 2]\n", [1, 2], "answer"),
        ('"text"', "text", "answer"),
        ('Here it is:\n```json\n{"a": 2}\n```\nDone.', {"a": 2}, "json_block"),
        ('```JSON\n{"a": 3}\n```', {"a": 3}, "json_block"),
        ("Notes:\n```python\nprint(1)\n```\n```json\n[true]\n```", [True], "json_block"),
    ],
)
def test_extract_json(answer: str, value: Any, source: str) -> None:
    assert extract_json(answer) == (value, source)


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        ("   ", "the final answer is empty"),
        ("synthesized plan from 3 observations", "no JSON document found"),
        ('{"a": 1,}', "the answer is not valid JSON: Expecting property name"),
        ('{"a": 1} and more', "the answer is not valid JSON: Extra data"),
        ('{"a": NaN}', "NaN is not valid JSON"),
        ('{"a": 1, "a": 2}', 'duplicate object key "a"'),
        ("```json\n{}\n```\n```json\n[]\n```", "the answer has 2 ```json blocks; return exactly one JSON document"),
        ('```json\n{"a": 1}', "the ```json block is not closed"),
        ('```json\n{"a": }\n```', "the ```json block is not valid JSON"),
        ("[" * 100_000, "nests too deeply"),
    ],
)
def test_extract_json_errors(answer: str, message: str) -> None:
    with pytest.raises(OutputExtractionError) as raised:
        extract_json(answer)
    assert message in str(raised.value)


def test_check_output_reports_extraction_size_and_schema_errors() -> None:
    schema = OutputSchema.from_value({"type": "object", "required": ["ok"]})
    assert check_output("not json", schema).errors[0].startswith("$: no JSON document found")
    assert not check_output("not json", schema).found
    invalid = check_output("{}", schema)
    assert invalid.found and not invalid.valid and invalid.errors == ("$.ok: required property is missing",)
    valid = check_output('```json\n{"ok": true}\n```', schema)
    assert valid.valid and valid.value == {"ok": True} and valid.source == "json_block" and valid.output_bytes == 11
    huge = check_output(json.dumps({"ok": "x" * MAX_OUTPUT_BYTES}), schema)
    assert not huge.found and "the limit is 65536" in huge.errors[0]
    deep = check_output("[" * 70 + "]" * 70, OutputSchema.from_value(True))
    assert deep.errors == ("$: the JSON document nests deeper than 64 levels",)


def test_contract_payload_round_trip_and_tamper_check() -> None:
    contract = OutputContract(schema=OutputSchema.from_value({"type": "string"}, source="s.json"), retries=1)
    payload = contract.to_payload()
    assert payload == {
        "schema": {"type": "string"},
        "schema_sha256": contract.schema.sha256,
        "source": "s.json",
        "retries": 1,
    }
    restored = OutputContract.from_payload(payload)
    assert restored == contract and restored.max_attempts == 2
    with pytest.raises(SchemaError, match="does not match its sha256 digest"):
        OutputContract.from_payload({**payload, "schema": {"type": "number"}})
    with pytest.raises(SchemaError, match="malformed"):
        OutputContract.from_payload({**payload, "retries": 11})
    with pytest.raises(ValueError, match="between 0 and 10"):
        OutputContract(schema=contract.schema, retries=-1)


def test_example_instance_validates_for_common_schemas() -> None:
    schema = OutputSchema.from_value(
        {
            "type": "object",
            "required": ["title", "steps", "risk", "count", "ok", "note"],
            "additionalProperties": False,
            "properties": {
                "title": {"type": "string", "minLength": 3, "maxLength": 10},
                "steps": {"type": "array", "items": {"$ref": "#/$defs/step"}, "minItems": 3, "uniqueItems": True},
                "risk": {"enum": ["low", "high"]},
                "count": {"type": "integer", "exclusiveMinimum": 0, "maximum": 4},
                "ok": {"type": "boolean"},
                "note": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            },
            "$defs": {"step": {"type": "string", "minLength": 2}},
        }
    )
    document = example_instance(schema, text="Plan the launch", items=["a1", "b2"])
    assert schema.validate(document) == ()
    assert document["steps"] == ["a1", "b2", "Plan the launch 3"] and document["count"] == 2


def test_write_output_file_is_atomic_and_sorted(tmp_path: Path) -> None:
    target = tmp_path / "out" / "result.json"
    write_output_file(target, {"b": 1, "a": "é"})
    assert target.read_text(encoding="utf-8") == '{\n  "a": "é",\n  "b": 1\n}\n'
    write_output_file(target, [1])
    assert json.loads(target.read_text(encoding="utf-8")) == [1]
    assert sorted(path.name for path in target.parent.iterdir()) == ["result.json"]


def _doubling_chain(levels: int) -> dict[str, Any]:
    """Each definition applies the previous one twice: small, acyclic, and 2**levels checks per value."""

    definitions: dict[str, Any] = {"d0": {"type": "integer"}}
    for level in range(1, levels + 1):
        reference = {"$ref": f"#/$defs/d{level - 1}"}
        definitions[f"d{level}"] = {"allOf": [reference, reference]}
    return {"$defs": definitions, "$ref": f"#/$defs/d{levels}"}


def test_references_that_multiply_validation_work_are_refused() -> None:
    with pytest.raises(SchemaError) as raised:
        OutputSchema.from_value(_doubling_chain(30))
    assert "expand to more than" in str(raised.value)


def test_validation_work_is_bounded_when_references_multiply_through_items() -> None:
    schema = OutputSchema.from_value(
        {
            "$defs": {
                "x": {"allOf": [{"$ref": "#/$defs/y"}, {"$ref": "#/$defs/y"}]},
                "y": {"items": {"$ref": "#/$defs/x"}},
            },
            "$ref": "#/$defs/x",
        }
    )
    nested: Any = 0
    for _ in range(17):
        nested = [nested]
    errors = schema.validate(nested)
    assert len(errors) == 1 and "validation stopped after" in errors[0]


@pytest.mark.parametrize("answer", ["1e400", '{"x": [-1e400]}', '"\\ud800"', '{"\\udfff": 1}'])
def test_answers_that_cannot_be_stored_are_invalid_answers(answer: str) -> None:
    check = check_output(answer, OutputSchema.from_value(True))
    assert not check.valid and not check.found
    assert len(check.errors) == 1 and check.errors[0].startswith("$: ")
