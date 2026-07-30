"""Deterministic HTML-to-Markdown conversion tool.

Agent runs often receive HTML fragments — scraped page snippets, email bodies,
or tool payloads wrapped in tags — and need Markdown for handoffs. Asking a
language model to invent Markdown is unreliable (dropped links, broken lists,
leaked ``<script>``). This tool converts a constrained HTML subset to Markdown
via the standard-library :class:`html.parser.HTMLParser`, rejects documents that
contain executable ``script`` (or ``style``) content, and returns a structured
failure for empty or oversized input. It never executes code and never makes a
network request, matching the ``html_strip``, ``html_table``, ``diff``, and
``json_format`` tool contracts. Safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import html as html_lib
import re
from html.parser import HTMLParser
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_REJECTED_TAGS: Final[frozenset[str]] = frozenset({"script", "style"})
_HEADING_TAGS: Final[frozenset[str]] = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_BOLD_TAGS: Final[frozenset[str]] = frozenset({"strong", "b"})
_ITALIC_TAGS: Final[frozenset[str]] = frozenset({"em", "i"})
_MULTI_NEWLINE: Final[re.Pattern[str]] = re.compile(r"\n{3,}")
_TRAILING_WS: Final[re.Pattern[str]] = re.compile(r"[ \t]+\n")
_LEADING_WS: Final[re.Pattern[str]] = re.compile(r"\n[ \t]+")


def _attr_map(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    """Build a lowercased attribute map, dropping ``None`` values.

    Args:
        attrs: Attribute name/value pairs from :class:`HTMLParser`.

    Returns:
        Mapping of lowercased attribute names to string values.
    """

    return {name.lower(): value for name, value in attrs if value is not None}


class _MarkdownParser(HTMLParser):
    """Accumulate Markdown while tracking rejected tags and nesting."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.rejected_tag: str | None = None
        self._skip_depth = 0
        self._list_stack: list[str] = []
        self._ol_counters: list[int] = []
        self._link_stack: list[str | None] = []
        self._pre_depth = 0
        self._code_depth = 0
        self._pending_block_break = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Enter a tag and emit Markdown open markers.

        Args:
            tag: Element name.
            attrs: Attribute name/value pairs.
        """

        name = tag.lower()
        if name in _REJECTED_TAGS:
            self.rejected_tag = self.rejected_tag or name
            self._skip_depth += 1
            return
        if self._skip_depth:
            return

        attr = _attr_map(attrs)
        if name in _HEADING_TAGS:
            self._ensure_block_break()
            level = int(name[1])
            self.parts.append("#" * level + " ")
        elif name == "p":
            self._ensure_block_break()
        elif name == "br":
            self.parts.append("\n")
        elif name == "hr":
            self._ensure_block_break()
            self.parts.append("---\n\n")
        elif name == "ul":
            self._ensure_block_break()
            self._list_stack.append("ul")
        elif name == "ol":
            self._ensure_block_break()
            self._list_stack.append("ol")
            self._ol_counters.append(0)
        elif name == "li":
            self._ensure_line_break()
            depth = max(len(self._list_stack) - 1, 0)
            indent = "  " * depth
            if self._list_stack and self._list_stack[-1] == "ol":
                self._ol_counters[-1] += 1
                self.parts.append(f"{indent}{self._ol_counters[-1]}. ")
            else:
                self.parts.append(f"{indent}- ")
        elif name == "a":
            self._link_stack.append(attr.get("href"))
            self.parts.append("[")
        elif name in _BOLD_TAGS:
            self.parts.append("**")
        elif name in _ITALIC_TAGS:
            self.parts.append("*")
        elif name == "code" and self._pre_depth == 0:
            self._code_depth += 1
            self.parts.append("`")
        elif name == "pre":
            self._ensure_block_break()
            self._pre_depth += 1
            self.parts.append("```\n")
        elif name == "blockquote":
            self._ensure_block_break()
            self.parts.append("> ")

    def handle_endtag(self, tag: str) -> None:
        """Leave a tag and emit Markdown close markers.

        Args:
            tag: Element name.
        """

        name = tag.lower()
        if name in _REJECTED_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return

        if name in _HEADING_TAGS or name == "p":
            self.parts.append("\n\n")
            self._pending_block_break = False
        elif name == "ul":
            if self._list_stack and self._list_stack[-1] == "ul":
                self._list_stack.pop()
            self.parts.append("\n")
            self._pending_block_break = False
        elif name == "ol":
            if self._list_stack and self._list_stack[-1] == "ol":
                self._list_stack.pop()
            if self._ol_counters:
                self._ol_counters.pop()
            self.parts.append("\n")
            self._pending_block_break = False
        elif name == "li":
            self.parts.append("\n")
        elif name == "a":
            href = self._link_stack.pop() if self._link_stack else None
            if href:
                self.parts.append(f"]({href})")
            else:
                self.parts.append("]")
        elif name in _BOLD_TAGS:
            self.parts.append("**")
        elif name in _ITALIC_TAGS:
            self.parts.append("*")
        elif name == "code" and self._pre_depth == 0 and self._code_depth:
            self._code_depth -= 1
            self.parts.append("`")
        elif name == "pre" and self._pre_depth:
            self._pre_depth -= 1
            if self.parts and not self.parts[-1].endswith("\n"):
                self.parts.append("\n")
            self.parts.append("```\n\n")
            self._pending_block_break = False
        elif name == "blockquote":
            self.parts.append("\n\n")
            self._pending_block_break = False

    def handle_data(self, data: str) -> None:
        """Append character data when not inside a rejected tag.

        Args:
            data: Raw text node content.
        """

        if self._skip_depth or not data:
            return
        if self._pre_depth:
            self.parts.append(data)
            return
        # Collapse horizontal whitespace outside ``<pre>``.
        collapsed = re.sub(r"[ \t\f\v]+", " ", data)
        if collapsed:
            self.parts.append(collapsed)

    def handle_entityref(self, name: str) -> None:
        """Append a named character entity when not inside a rejected tag.

        Args:
            name: Entity name without the leading ``&`` / trailing ``;``.
        """

        if self._skip_depth:
            return
        self.parts.append(html_lib.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        """Append a numeric character reference when not inside a rejected tag.

        Args:
            name: Decimal or hex code point text.
        """

        if self._skip_depth:
            return
        self.parts.append(html_lib.unescape(f"&{name};" if name.startswith("#") else f"&#{name};"))

    def _ensure_block_break(self) -> None:
        """Ensure the next block starts after a blank line when needed."""

        if not self.parts:
            return
        joined_tail = "".join(self.parts[-3:])
        if joined_tail.endswith("\n\n"):
            return
        if joined_tail.endswith("\n"):
            self.parts.append("\n")
        else:
            self.parts.append("\n\n")

    def _ensure_line_break(self) -> None:
        """Ensure the next list item starts on a new line."""

        if not self.parts:
            return
        if not "".join(self.parts[-2:]).endswith("\n"):
            self.parts.append("\n")


class HtmlMarkdownTool:
    """Convert HTML fragments to Markdown, rejecting script/style documents."""

    name = "html_markdown"
    description = (
        "Converts HTML fragments to Markdown "
        "(headings/links/lists/bold/italic/code/paragraphs; rejects script/style; "
        "empty/oversized → ok=False)."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Convert HTML in the invocation text to Markdown.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the HTML
                fragment to convert.

        Returns:
            Tool result whose ``content`` is Markdown, or ``ok=False`` and an
            explanation when the document is empty, too long, or contains a
            ``script`` / ``style`` element.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document.strip():
            return self._fail("document is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        parser = _MarkdownParser()
        try:
            parser.feed(document)
            parser.close()
        except (AssertionError, ValueError, TypeError) as exc:
            return self._fail(f"could not parse HTML: {exc}", {})

        if parser.rejected_tag is not None:
            return self._fail(
                f"document contains rejected <{parser.rejected_tag}> content",
                {"rejected_tag": parser.rejected_tag},
            )

        markdown = self._normalize("".join(parser.parts))
        if not markdown:
            return self._fail("document reduces to empty markdown", {})

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=markdown,
            metadata={"chars": len(markdown), "source_chars": len(document)},
        )

    @staticmethod
    def _normalize(text: str) -> str:
        """Trim and collapse excessive blank lines in Markdown output.

        Args:
            text: Raw concatenated Markdown fragments.

        Returns:
            Trimmed Markdown with at most one blank line between blocks.
        """

        cleaned = _TRAILING_WS.sub("\n", text)
        cleaned = _LEADING_WS.sub("\n", cleaned)
        cleaned = _MULTI_NEWLINE.sub("\n\n", cleaned)
        return cleaned.strip()

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result.

        Args:
            message: Human-readable failure explanation.
            metadata: Structured metadata for the failure.

        Returns:
            A ``ok=False`` tool result carrying the message and metadata.
        """

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
