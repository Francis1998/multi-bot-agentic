"""Deterministic HTML-to-text stripping tool.

Agent runs routinely ingest HTML fragments: a scraped page snippet, an email
body, or a tool payload wrapped in tags. Asking a language model to invent the
plain-text form is unreliable (kept tags, dropped entities, leaked
``<script>``). This tool strips markup to readable text via the standard-library
:class:`html.parser.HTMLParser`, rejects documents that contain executable
``script`` (or ``style``) content, and returns a structured failure for empty or
oversized input. It never executes code and never makes a network request,
matching the ``diff``, ``regex``, ``hash``, ``slugify``, and ``json_format``
tool contracts.
"""

from __future__ import annotations

import html as html_lib
import re
from html.parser import HTMLParser
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
# Tags whose body must never surface as plain text (XSS / CSS injection risk).
_REJECTED_TAGS: Final[frozenset[str]] = frozenset({"script", "style"})
# Block-ish tags that should introduce a word/line break so adjacent text does
# not glue together after tags are removed (``</p><p>next`` → ``next`` with a
# space rather than ``next`` jammed onto the previous word).
_BREAK_TAGS: Final[frozenset[str]] = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tr",
        "ul",
    }
)
_WHITESPACE: Final[re.Pattern[str]] = re.compile(r"[ \t\f\v]+")
_MULTI_NEWLINE: Final[re.Pattern[str]] = re.compile(r"\n{3,}")


class _StripParser(HTMLParser):
    """Accumulate visible text while tracking rejected / break tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.rejected_tag: str | None = None
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Enter a tag; record rejected tags and emit breaks for block tags.

        Args:
            tag: Lowercased element name.
            attrs: Attribute name/value pairs (unused; kept for HTMLParser API).
        """

        del attrs  # Attributes are discarded; we only extract visible text.
        name = tag.lower()
        if name in _REJECTED_TAGS:
            self.rejected_tag = self.rejected_tag or name
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if name in _BREAK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """Leave a tag; exit skip regions and emit trailing breaks.

        Args:
            tag: Lowercased element name.
        """

        name = tag.lower()
        if name in _REJECTED_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if name in _BREAK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        """Append character data when not inside a rejected tag.

        Args:
            data: Raw text node content.
        """

        if self._skip_depth:
            return
        if data:
            self.parts.append(data)

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
            name: Decimal or hex code point text (``#`` prefix optional per parser).
        """

        if self._skip_depth:
            return
        self.parts.append(html_lib.unescape(f"&{name};" if name.startswith("#") else f"&#{name};"))


class HtmlStripTool:
    """Strip HTML markup to plain text, rejecting script/style documents."""

    name = "html_strip"
    description = "Strips HTML tags to plain text (rejects script/style; empty/oversized → ok=False)."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Strip HTML from the document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the HTML
                document to convert to plain text.

        Returns:
            Tool result whose ``content`` is the stripped plain text, or
            ``ok=False`` and an explanation when the document is empty, too long,
            or contains a ``script`` / ``style`` element.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document.strip():
            return self._fail("document is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        parser = _StripParser()
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

        plain = self._normalize("".join(parser.parts))
        if not plain:
            return self._fail("document reduces to empty text", {})

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=plain,
            metadata={"chars": len(plain), "source_chars": len(document)},
        )

    @staticmethod
    def _normalize(text: str) -> str:
        """Collapse runs of whitespace while preserving paragraph breaks.

        Args:
            text: Raw concatenated text nodes.

        Returns:
            Trimmed text with horizontal whitespace collapsed and more than two
            consecutive newlines reduced to a blank line.
        """

        collapsed = _WHITESPACE.sub(" ", text)
        collapsed = _MULTI_NEWLINE.sub("\n\n", collapsed)
        # Trim spaces around newlines introduced by block tags.
        collapsed = re.sub(r" *\n *", "\n", collapsed)
        return collapsed.strip()

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result.

        Args:
            message: Human-readable failure explanation.
            metadata: Structured metadata for the failure.

        Returns:
            A ``ok=False`` tool result carrying the message and metadata.
        """

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
