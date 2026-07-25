"""Deterministic template rendering tool.

Agent runs routinely need to fill short artifacts: email snippets, issue
summaries, prompt fragments, or provider comparison tables. Asking a language
model to perform final substitution is unreliable (missed variables, accidental
raw HTML, inconsistent whitespace). This tool renders simple ``{name}`` or
``{{ name }}`` placeholders with a caller-supplied JSON object, escapes every
substituted value, and enforces hard size caps. It never evaluates expressions,
imports code, calls filters, or makes a network request, matching the ``csv``,
``regex``, ``truncate``, and ``json_format`` tool contracts.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:template_render:<payload>``, the template and variables may be supplied
either as separate ``template`` / ``variables`` arguments (tests and
programmatic callers) or as a single ``text`` value split on the sentinel
``<<<TEMPLATE_VARS>>>``.
"""

from __future__ import annotations

import html
import json
import math
import re
from collections.abc import Mapping
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_TEMPLATE_CHARS: Final[int] = 20_000
_MAX_VARIABLES: Final[int] = 100
_MAX_VARIABLE_NAME_CHARS: Final[int] = 64
_MAX_VARIABLE_VALUE_CHARS: Final[int] = 4_000
_MAX_OUTPUT_CHARS: Final[int] = 40_000
_SPLIT_SENTINEL: Final[str] = "<<<TEMPLATE_VARS>>>"
_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PLACEHOLDER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}|{([A-Za-z_][A-Za-z0-9_]*)}"
)


class TemplateRenderTool:
    """Render simple placeholders with escaped scalar values."""

    name = "template_render"
    description = (
        "Renders simple {var} / {{ var }} templates from JSON variables; escapes values; no eval; bounded output."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Render a template using escaped caller-supplied variables.

        Args:
            invocation: Tool invocation whose arguments hold either
                ``template`` + ``variables`` or a single ``text`` split on
                ``<<<TEMPLATE_VARS>>>`` with JSON variables on the right.

        Returns:
            Tool result whose ``content`` is the rendered text, or ``ok=False``
            and an explanation when the template/variables/output are invalid
            or exceed the configured caps.
        """

        template, raw_variables, error = self._resolve_inputs(invocation.arguments)
        if error is not None:
            return self._fail(error, {})

        assert template is not None and raw_variables is not None
        if not template:
            return self._fail("template is empty", {})
        if len(template) > _MAX_TEMPLATE_CHARS:
            return self._fail(
                f"template exceeds max_chars={_MAX_TEMPLATE_CHARS}",
                {"chars": len(template)},
            )

        variables, error = self._normalize_variables(raw_variables)
        if error is not None:
            return self._fail(error, {})

        rendered_parts: list[str] = []
        last_end = 0
        placeholders: list[str] = []
        for match in _PLACEHOLDER_PATTERN.finditer(template):
            literal = template[last_end : match.start()]
            if "{" in literal or "}" in literal:
                return self._fail("template contains unsupported brace syntax", {})
            name = match.group(1) or match.group(2)
            placeholders.append(name)
            if name not in variables:
                return self._fail(f"missing variable: {name}", {"missing": name})
            rendered_parts.append(literal)
            rendered_parts.append(variables[name])
            last_end = match.end()

        tail = template[last_end:]
        if "{" in tail or "}" in tail:
            return self._fail("template contains unsupported brace syntax", {})
        rendered_parts.append(tail)

        rendered = "".join(rendered_parts)
        if len(rendered) > _MAX_OUTPUT_CHARS:
            return self._fail(
                f"rendered output exceeds max_chars={_MAX_OUTPUT_CHARS}",
                {"chars": len(rendered)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=rendered,
            metadata={
                "escaped": True,
                "placeholder_count": len(placeholders),
                "unique_placeholders": sorted(set(placeholders)),
                "chars": len(rendered),
            },
        )

    @classmethod
    def _resolve_inputs(cls, arguments: dict[str, object]) -> tuple[str | None, object | None, str | None]:
        """Resolve a template and variables from structured args or a sentinel.

        Args:
            arguments: Tool invocation arguments.

        Returns:
            ``(template, variables, error)`` with exactly one successful pair or
            one error string populated.
        """

        if "template" in arguments or "variables" in arguments:
            if "template" not in arguments:
                return None, None, "template argument is required"
            if "variables" not in arguments:
                return None, None, "variables argument is required"
            return str(arguments.get("template", "")), arguments.get("variables"), None

        text = str(arguments.get("text", ""))
        if _SPLIT_SENTINEL not in text:
            return (
                None,
                None,
                (f"template_render requires template+variables arguments, or text split on {_SPLIT_SENTINEL!r}"),
            )
        template, variables_json = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in variables_json:
            return None, None, "text contains more than one <<<TEMPLATE_VARS>>> sentinel"
        variables_json = variables_json.strip()
        if not variables_json:
            return None, None, "variables JSON is empty"
        try:
            variables = json.loads(variables_json)
        except json.JSONDecodeError as exc:
            return None, None, f"invalid variables JSON: {exc.msg}"
        return template, variables, None

    @classmethod
    def _normalize_variables(cls, raw_variables: object) -> tuple[dict[str, str], str | None]:
        """Validate and escape a mapping of scalar variable values.

        Args:
            raw_variables: Caller-provided variables object.

        Returns:
            Escaped string variables and an optional error message.
        """

        if not isinstance(raw_variables, Mapping):
            return {}, "variables must be an object"
        if len(raw_variables) > _MAX_VARIABLES:
            return {}, f"variables exceed max_count={_MAX_VARIABLES}"

        variables: dict[str, str] = {}
        for key, value in raw_variables.items():
            name = str(key)
            if len(name) > _MAX_VARIABLE_NAME_CHARS or _NAME_PATTERN.fullmatch(name) is None:
                return {}, f"invalid variable name: {name!r}"
            value_text, error = cls._coerce_scalar(value)
            if error is not None:
                return {}, f"variable {name!r} {error}"
            if len(value_text) > _MAX_VARIABLE_VALUE_CHARS:
                return {}, f"variable {name!r} exceeds max_chars={_MAX_VARIABLE_VALUE_CHARS}"
            variables[name] = html.escape(value_text, quote=True)
        return variables, None

    @staticmethod
    def _coerce_scalar(value: object) -> tuple[str, str | None]:
        """Coerce one JSON-like scalar value into deterministic text.

        Args:
            value: Raw variable value.

        Returns:
            ``(text, error)`` with an error for nested objects/arrays or
            non-finite floats.
        """

        if value is None:
            return "", None
        if isinstance(value, bool):
            return ("true" if value else "false"), None
        if isinstance(value, int):
            return str(value), None
        if isinstance(value, float):
            if not math.isfinite(value):
                return "", "must be finite"
            return str(value), None
        if isinstance(value, str):
            return value, None
        return "", "must be a string, number, boolean, or null"

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result.

        Args:
            message: Human-readable failure explanation.
            metadata: Structured metadata for the failure.

        Returns:
            A ``ok=False`` tool result carrying the message and metadata.
        """

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
