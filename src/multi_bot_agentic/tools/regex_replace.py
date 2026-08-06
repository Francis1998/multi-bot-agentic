"""Bounded regex find/replace tool for agent text handoffs.

Agents often need a deterministic find/replace before the next LLM turn.
Asking a language model to invent replacements drifts across turns and can
corrupt surrounding text. This tool compiles a Python regular expression and
applies a bounded substitution via stdlib :mod:`re`. Patterns are length-capped
and match counts are limited to reduce catastrophic backtracking risk. It never
executes code and never makes network requests. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
"""

from __future__ import annotations

import re
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_PATTERN_CHARS: Final[int] = 200
_MAX_REPL_CHARS: Final[int] = 2_000
_MAX_MATCHES: Final[int] = 100
_DEFAULT_COUNT: Final[int] = 0  # 0 means replace up to _MAX_MATCHES


class RegexReplaceTool:
    """Apply a bounded regex find/replace to a text document."""

    name = "regex_replace"
    description = (
        "Bounded regex find/replace (text, pattern, repl; optional count); "
        "rejects oversized/catastrophic patterns; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Replace regex matches in the document.

        Args:
            invocation: Tool invocation whose ``text`` holds the document,
                ``pattern`` is the regex, ``repl`` is the replacement string,
                and optional ``count`` limits replacements (0 = all up to the
                match cap).

        Returns:
            Tool result with the rewritten text, or ``ok=False`` when input is
            empty, oversized, the pattern is invalid/rejected, or match count
            exceeds the safety cap.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        pattern = str(invocation.arguments.get("pattern", ""))
        if not pattern:
            return self._fail("pattern is empty", {})
        if len(pattern) > _MAX_PATTERN_CHARS:
            return self._fail(
                f"pattern exceeds max_chars={_MAX_PATTERN_CHARS}",
                {"chars": len(pattern)},
            )
        rejected = self._reject_catastrophic(pattern)
        if rejected is not None:
            return self._fail(rejected, {"pattern": pattern})

        if "repl" not in invocation.arguments:
            return self._fail("repl is required", {})
        repl = str(invocation.arguments.get("repl", ""))
        if len(repl) > _MAX_REPL_CHARS:
            return self._fail(
                f"repl exceeds max_chars={_MAX_REPL_CHARS}",
                {"chars": len(repl)},
            )

        count_raw = invocation.arguments.get("count", _DEFAULT_COUNT)
        try:
            count = int(str(count_raw).strip())
        except ValueError:
            return self._fail(
                f"count must be an integer, got {count_raw!r}",
                {"count": str(count_raw)},
            )
        if count < 0:
            return self._fail("count must be >= 0", {"count": count})

        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            return self._fail(f"invalid regex: {exc}", {"pattern": pattern})

        # Cap matches regardless of count=0 (all) to bound backtracking cost.
        effective_limit = _MAX_MATCHES if count == 0 else min(count, _MAX_MATCHES)
        match_count = 0
        for _match in compiled.finditer(document):
            match_count += 1
            if match_count > _MAX_MATCHES:
                return self._fail(
                    f"match count exceeds max_matches={_MAX_MATCHES}",
                    {"matches": match_count},
                )

        if count == 0 and match_count > _MAX_MATCHES:
            return self._fail(
                f"match count exceeds max_matches={_MAX_MATCHES}",
                {"matches": match_count},
            )

        replaced, n = compiled.subn(repl, document, count=effective_limit)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=replaced,
            metadata={
                "replacements": n,
                "pattern": pattern,
                "chars": len(replaced),
            },
        )

    @staticmethod
    def _reject_catastrophic(pattern: str) -> str | None:
        """Reject patterns that are likely to cause catastrophic backtracking.

        Heuristics only — length is the primary bound; nested quantifiers on
        quantified groups are refused as an extra guard.
        """

        # Nested quantifiers like (a+)+ or (a*){2,} are classic ReDoS shapes.
        if re.search(r"\([^)]*[+*][^)]*\)[+*{]", pattern):
            return "pattern rejected: nested quantifiers are not allowed"
        if pattern.count("(") > 20 or pattern.count(")") > 20:
            return "pattern rejected: too many capturing groups"
        if pattern.count("|") > 30:
            return "pattern rejected: too many alternations"
        return None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
