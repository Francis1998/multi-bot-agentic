"""Tests for ToolResultSchemaValidator."""

from __future__ import annotations

import pytest

from multi_bot_agentic.models import ToolResult
from multi_bot_agentic.schema_validate import (
    ToolResultSchemaValidator,
    is_json_compatible,
)


def test_valid_success_result() -> None:
    """Well-formed successful result validates."""

    result = ToolResult(tool_name="echo", ok=True, content="hello", metadata={"n": 1})
    outcome = ToolResultSchemaValidator().validate(result)
    assert outcome.ok
    assert outcome.issues == ()


def test_empty_content_on_success_fails() -> None:
    """Successful results with blank content fail by default."""

    result = ToolResult(tool_name="echo", ok=True, content="  ", metadata={})
    outcome = ToolResultSchemaValidator().validate(result)
    assert not outcome.ok
    assert any(issue.path == "content" for issue in outcome.issues)


def test_required_metadata_keys() -> None:
    """Missing required metadata keys are reported."""

    result = ToolResult(tool_name="echo", ok=True, content="ok", metadata={})
    validator = ToolResultSchemaValidator(required_metadata_keys=frozenset({"request_id"}))
    outcome = validator.validate(result)
    assert not outcome.ok
    assert any("request_id" in issue.path for issue in outcome.issues)


def test_metadata_type_check() -> None:
    """Wrong metadata value types are reported."""

    result = ToolResult(tool_name="echo", ok=True, content="ok", metadata={"n": "x"})
    validator = ToolResultSchemaValidator(metadata_value_types={"n": int})
    outcome = validator.validate(result)
    assert not outcome.ok


def test_assert_valid_raises() -> None:
    """assert_valid raises ValueError on invalid results."""

    result = ToolResult(tool_name="", ok=True, content="x", metadata={})
    with pytest.raises(ValueError, match="schema invalid"):
        ToolResultSchemaValidator().assert_valid(result)


def test_is_json_compatible() -> None:
    """JSON compatibility helper accepts nested stdlib types only."""

    assert is_json_compatible({"a": [1, True, None, "x"]})
    assert not is_json_compatible({"a": {1, 2}})
