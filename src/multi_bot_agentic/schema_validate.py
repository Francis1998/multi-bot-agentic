"""Tool-result schema validator for multi-bot tool loops.

Validates ``ToolResult`` shape and optional JSON-like metadata contracts before
observations are fed back into the decision engine. Distinct from pydantic
tool-calling schemas in LangChain/CrewAI — this is a lightweight, stdlib-only
guardrail for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 tool loops.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from multi_bot_agentic.models import ToolResult


@dataclass(frozen=True)
class SchemaIssue:
    """One validation issue found on a tool result.

    Attributes:
        path: Dot-path to the offending field.
        message: Human-readable explanation.
    """

    path: str
    message: str


@dataclass(frozen=True)
class SchemaValidationResult:
    """Outcome of validating a tool result.

    Attributes:
        ok: True when no issues were found.
        issues: Tuple of schema issues (empty when ok).
    """

    ok: bool
    issues: tuple[SchemaIssue, ...]


class ToolResultSchemaValidator:
    """Validate ToolResult structure and optional metadata schema.

    Args:
        require_non_empty_content_on_success: When True, successful results
            must include non-blank content.
        required_metadata_keys: Keys that must exist in metadata when provided.
        metadata_value_types: Optional mapping of metadata key -> expected type.
    """

    def __init__(
        self,
        *,
        require_non_empty_content_on_success: bool = True,
        required_metadata_keys: frozenset[str] | None = None,
        metadata_value_types: dict[str, type] | None = None,
    ) -> None:
        self._require_content = require_non_empty_content_on_success
        self._required_keys = required_metadata_keys or frozenset()
        self._type_map = dict(metadata_value_types or {})

    def validate(self, result: ToolResult) -> SchemaValidationResult:
        """Validate a tool result.

        Args:
            result: ToolResult produced by a ToolAdapter.

        Returns:
            SchemaValidationResult with ok flag and issues.
        """

        issues: list[SchemaIssue] = []
        if not isinstance(result.tool_name, str) or not result.tool_name.strip():
            issues.append(SchemaIssue("tool_name", "must be a non-empty string"))
        if not isinstance(result.ok, bool):
            issues.append(SchemaIssue("ok", "must be a bool"))
        if not isinstance(result.content, str):
            issues.append(SchemaIssue("content", "must be a string"))
        elif result.ok and self._require_content and not result.content.strip():
            issues.append(SchemaIssue("content", "successful results require non-empty content"))
        if not isinstance(result.metadata, dict):
            issues.append(SchemaIssue("metadata", "must be a dict"))
            return SchemaValidationResult(ok=False, issues=tuple(issues))

        for key in sorted(self._required_keys):
            if key not in result.metadata:
                issues.append(SchemaIssue(f"metadata.{key}", "required key missing"))

        for key, expected in sorted(self._type_map.items()):
            if key not in result.metadata:
                continue
            value = result.metadata[key]
            if not isinstance(value, expected):
                issues.append(
                    SchemaIssue(
                        f"metadata.{key}",
                        f"expected {expected.__name__}, got {type(value).__name__}",
                    )
                )

        return SchemaValidationResult(ok=not issues, issues=tuple(issues))

    def assert_valid(self, result: ToolResult) -> ToolResult:
        """Validate and return the result, or raise ValueError.

        Args:
            result: ToolResult to validate.

        Returns:
            The same result when valid.

        Raises:
            ValueError: When validation fails.
        """

        outcome = self.validate(result)
        if not outcome.ok:
            details = "; ".join(f"{issue.path}: {issue.message}" for issue in outcome.issues)
            raise ValueError(f"tool result schema invalid: {details}")
        return result


def is_json_compatible(value: Any) -> bool:
    """Return True if value is JSON-serializable with stdlib types only.

    Args:
        value: Arbitrary Python value.

    Returns:
        True for None/bool/int/float/str and nested list/dict thereof.
    """

    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, list):
        return all(is_json_compatible(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and is_json_compatible(item) for key, item in value.items())
    return False
