"""Deterministic semantic-version comparison tool.

DevOps and packaging agents often need to gate on whether one version is
newer than another before the next LLM turn. Asking a model to compare
``1.0.0-alpha`` vs ``1.0.0`` is error-prone. This tool implements SemVer 2.0.0
precedence for ``major.minor.patch`` with optional pre-release identifiers
(build metadata is ignored for comparison). It never executes code and never
makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.

Versions may be supplied as separate ``version_a`` / ``version_b`` arguments
or as one ``text`` value split on ``<<<SEMVER_COMPARE>>>``.
"""

from __future__ import annotations

import re
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_VERSION_CHARS: Final[int] = 128
_SPLIT_SENTINEL: Final[str] = "<<<SEMVER_COMPARE>>>"
_SEMVER_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


class SemverCompareTool:
    """Compare two semantic versions and return -1, 0, or 1."""

    name = "semver_compare"
    description = (
        "Compares two SemVer versions (major.minor.patch with optional pre-release); "
        "returns -1/0/1 plus a human summary; accepts version_a+version_b or <<<SEMVER_COMPARE>>>."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Compare two semantic versions.

        Args:
            invocation: Tool invocation with ``version_a`` and ``version_b``,
                or a single ``text`` payload split on ``<<<SEMVER_COMPARE>>>``.

        Returns:
            Tool result whose content is ``-1``, ``0``, or ``1`` followed by a
            human-readable comparison line, or ``ok=False`` for invalid input.
        """

        version_a, version_b, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert version_a is not None and version_b is not None

        for label, value in (("version_a", version_a), ("version_b", version_b)):
            if not value.strip():
                return self._fail(f"{label} is empty", {})
            if len(value) > _MAX_VERSION_CHARS:
                return self._fail(
                    f"{label} exceeds max_chars={_MAX_VERSION_CHARS}",
                    {"chars": len(value), "version": label},
                )

        parsed_a, error_a = self._parse_version(version_a.strip())
        if error_a is not None:
            return self._fail(error_a, {"version": "version_a", "value": version_a.strip()})
        parsed_b, error_b = self._parse_version(version_b.strip())
        if error_b is not None:
            return self._fail(error_b, {"version": "version_b", "value": version_b.strip()})
        assert parsed_a is not None and parsed_b is not None

        cmp = self._compare(parsed_a, parsed_b)
        left = version_a.strip()
        right = version_b.strip()
        if cmp < 0:
            relation = f"{left} < {right}"
        elif cmp > 0:
            relation = f"{left} > {right}"
        else:
            relation = f"{left} == {right}"

        content = f"{cmp}\n{relation}\n"
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "cmp": cmp,
                "version_a": left,
                "version_b": right,
                "relation": relation.strip(),
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, str | None, str | None]:
        """Resolve versions from explicit args or sentinel syntax."""

        if "version_a" in arguments or "version_b" in arguments:
            if "version_a" not in arguments or "version_b" not in arguments:
                return None, None, "semver_compare requires version_a and version_b"
            return str(arguments["version_a"]), str(arguments["version_b"]), None

        text = str(arguments.get("text", ""))
        if _SPLIT_SENTINEL not in text:
            return (
                None,
                None,
                (
                    "semver_compare requires version_a+version_b arguments, "
                    f"or a single text split on {_SPLIT_SENTINEL!r}"
                ),
            )

        if text.count(_SPLIT_SENTINEL) != 1:
            return None, None, "text contains more than one <<<SEMVER_COMPARE>>> sentinel"

        left, right = text.split(_SPLIT_SENTINEL, maxsplit=1)
        return left.strip(), right.strip(), None

    @staticmethod
    def _parse_version(
        value: str,
    ) -> tuple[tuple[int, int, int, tuple[str, ...]] | None, str | None]:
        """Parse a SemVer core version with optional pre-release and build."""

        match = _SEMVER_RE.fullmatch(value)
        if match is None:
            return None, f"invalid semantic version: {value!r}"
        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch"))
        pre = match.group("pre")
        pre_parts: tuple[str, ...] = tuple(pre.split(".")) if pre else ()
        return (major, minor, patch, pre_parts), None

    @staticmethod
    def _compare(
        left: tuple[int, int, int, tuple[str, ...]],
        right: tuple[int, int, int, tuple[str, ...]],
    ) -> int:
        """Return -1/0/1 using SemVer 2.0.0 precedence rules."""

        for left_num, right_num in zip(left[:3], right[:3], strict=True):
            if left_num < right_num:
                return -1
            if left_num > right_num:
                return 1

        left_pre = left[3]
        right_pre = right[3]
        if not left_pre and not right_pre:
            return 0
        if not left_pre:
            return 1
        if not right_pre:
            return -1

        for left_id, right_id in zip(left_pre, right_pre, strict=False):
            left_digits = left_id.isdigit()
            right_digits = right_id.isdigit()
            if left_digits and right_digits:
                left_int = int(left_id)
                right_int = int(right_id)
                if left_int < right_int:
                    return -1
                if left_int > right_int:
                    return 1
                continue
            if left_digits and not right_digits:
                return -1
            if right_digits and not left_digits:
                return 1
            if left_id < right_id:
                return -1
            if left_id > right_id:
                return 1

        if len(left_pre) < len(right_pre):
            return -1
        if len(left_pre) > len(right_pre):
            return 1
        return 0

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
