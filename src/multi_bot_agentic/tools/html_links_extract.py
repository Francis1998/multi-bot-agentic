"""Deterministic HTML link extractor.

Web-research agents (Browser-use / Scrapy-style pipelines) often need href +
anchor text without fetching pages. This tool parses HTML via stdlib
``html.parser``, returns canonical JSON of ``href``/``text`` pairs, rejects
``script``/``style`` documents, and never executes code or makes network
requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Arguments: ``html`` (or ``text``) plus optional ``max_links`` (default 100,
range 1..500).
"""

from __future__ import annotations

import json
from html.parser import HTMLParser
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_MAX_LINKS: Final[int] = 100
_MIN_MAX_LINKS: Final[int] = 1
_MAX_MAX_LINKS: Final[int] = 500
_FORBIDDEN_TAGS: Final[frozenset[str]] = frozenset({"script", "style"})


class _LinkCollector(HTMLParser):
    """Collect anchor href/text pairs while rejecting script/style."""

    def __init__(self, max_links: int) -> None:
        """Create a collector bounded by max_links."""

        super().__init__(convert_charrefs=True)
        self.max_links = max_links
        self.links: list[dict[str, str]] = []
        self._forbidden = False
        self._in_anchor = False
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track anchors and forbidden tags."""

        lowered = tag.lower()
        if lowered in _FORBIDDEN_TAGS:
            self._forbidden = True
            return
        if lowered != "a" or len(self.links) >= self.max_links:
            return
        attr_map = {key.lower(): (value or "") for key, value in attrs}
        href = attr_map.get("href", "").strip()
        if not href:
            return
        self._in_anchor = True
        self._current_href = href
        self._current_text = []

    def handle_endtag(self, tag: str) -> None:
        """Finalize an anchor entry."""

        if tag.lower() != "a" or not self._in_anchor:
            return
        self._in_anchor = False
        href = self._current_href or ""
        text = "".join(self._current_text).strip()
        self._current_href = None
        self._current_text = []
        if href and len(self.links) < self.max_links:
            self.links.append({"href": href, "text": text})

    def handle_data(self, data: str) -> None:
        """Accumulate anchor text."""

        if self._in_anchor:
            self._current_text.append(data)


class HtmlLinksExtractTool:
    """Extract href/text pairs from HTML anchors."""

    name = "html_links_extract"
    description = (
        "Extracts HTML anchor href+text pairs as JSON (max_links default 100); rejects script/style; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Extract links from the invocation HTML."""

        document, max_links, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and max_links is not None

        if not document.strip():
            return self._fail("html is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"html exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        collector = _LinkCollector(max_links=max_links)
        try:
            collector.feed(document)
            collector.close()
        except (AssertionError, TypeError, ValueError) as exc:
            return self._fail(f"html parse failed: {exc}", {})

        if collector._forbidden:
            return self._fail("html contains script or style", {})
        if not collector.links:
            return self._fail("no links found", {"max_links": max_links})

        content = json.dumps(collector.links, ensure_ascii=False, separators=(",", ":"))
        if len(content) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"links output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(content), "input_chars": len(document)},
            )
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "chars": len(content),
                "input_chars": len(document),
                "links": len(collector.links),
                "max_links": max_links,
            },
        )

    @classmethod
    def _resolve_arguments(cls, arguments: dict[str, object]) -> tuple[str | None, int | None, str | None]:
        """Resolve html/text and max_links."""

        document = str(arguments.get("html", "")) if "html" in arguments else str(arguments.get("text", ""))
        if "max_links" not in arguments:
            return document, _DEFAULT_MAX_LINKS, None
        max_links = cls._parse_max_links(arguments.get("max_links"))
        if max_links is None:
            return (
                None,
                None,
                (
                    f"max_links must be an integer {_MIN_MAX_LINKS}..{_MAX_MAX_LINKS}, "
                    f"got {arguments.get('max_links')!r}"
                ),
            )
        return document, max_links, None

    @staticmethod
    def _parse_max_links(value: object) -> int | None:
        """Parse a bounded max_links integer."""

        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            parsed = value
        elif isinstance(value, str) and value.strip().isdigit():
            parsed = int(value.strip())
        else:
            return None
        if not _MIN_MAX_LINKS <= parsed <= _MAX_MAX_LINKS:
            return None
        return parsed

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
