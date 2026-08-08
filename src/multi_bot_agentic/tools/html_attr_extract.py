"""HTML attribute extraction tool for agent markup handoffs.

Agents often need a single attribute (``href``, ``src``, ``id``, ``class``)
from an HTML snippet before the next LLM turn. Asking a language model to
invent attribute values drifts across turns and hallucinates URLs. This tool
walks markup with stdlib :class:`html.parser.HTMLParser` and returns matching
attribute values as newline-separated text. It never executes code and never
makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2.
"""

from __future__ import annotations

import json
from html.parser import HTMLParser
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_MAX_RESULTS: Final[int] = 100
_MAX_RESULTS_CAP: Final[int] = 500


class _AttrExtractParser(HTMLParser):
    """Collect attribute values matching an optional tag filter."""

    def __init__(self, attr: str, tag: str | None, max_results: int) -> None:
        super().__init__(convert_charrefs=True)
        self.attr = attr.lower()
        self.tag = tag.lower() if tag else None
        self.max_results = max_results
        self.values: list[str] = []
        self.truncated = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record matching attribute values from a start tag."""

        self._maybe_collect(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record matching attribute values from a self-closing tag."""

        self._maybe_collect(tag, attrs)

    def _maybe_collect(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Append attribute values when the tag filter matches."""

        if self.truncated:
            return
        name = tag.lower()
        if self.tag is not None and name != self.tag:
            return
        for attr_name, attr_value in attrs:
            if attr_name.lower() != self.attr:
                continue
            if len(self.values) >= self.max_results:
                self.truncated = True
                return
            self.values.append("" if attr_value is None else attr_value)


class HtmlAttrExtractTool:
    """Extract HTML attribute values for a simple tag/attr filter."""

    name = "html_attr_extract"
    description = (
        "Extracts HTML attribute values via stdlib html.parser "
        "(required attr; optional tag filter; max_results); max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Extract matching attribute values from the HTML document.

        Args:
            invocation: Tool invocation whose ``text`` argument holds HTML,
                ``attr`` is the required attribute name, optional ``tag``
                filters by element name, and optional ``max_results`` bounds
                how many values to return (default 100, cap 500).

        Returns:
            Tool result with newline-separated attribute values as content
            (and JSON array metadata), or ``ok=False`` when input is empty,
            oversized, or arguments are invalid.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        attr = str(invocation.arguments.get("attr", "")).strip()
        if not attr:
            return self._fail("attr is required", {})

        tag_raw = invocation.arguments.get("tag", "")
        tag = str(tag_raw).strip() or None

        max_results_raw = invocation.arguments.get("max_results", _DEFAULT_MAX_RESULTS)
        try:
            max_results = int(str(max_results_raw).strip())
        except ValueError:
            return self._fail(
                f"max_results must be an integer, got {max_results_raw!r}",
                {"max_results": str(max_results_raw)},
            )
        if max_results < 1:
            return self._fail("max_results must be >= 1", {"max_results": max_results})
        if max_results > _MAX_RESULTS_CAP:
            return self._fail(
                f"max_results exceeds max={_MAX_RESULTS_CAP}",
                {"max_results": max_results},
            )

        parser = _AttrExtractParser(attr=attr, tag=tag, max_results=max_results)
        try:
            parser.feed(document)
            parser.close()
        except (AssertionError, TypeError, ValueError) as exc:
            return self._fail(f"html parse error: {exc}", {"attr": attr})

        content = "\n".join(parser.values)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "attr": attr.lower(),
                "tag": tag.lower() if tag else "",
                "count": len(parser.values),
                "truncated": parser.truncated,
                "chars": len(content),
                "values_json": json.dumps(parser.values, ensure_ascii=False),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
