"""Deterministic HTML table extraction tool.

Agent runs often receive HTML snippets from docs, emails, dashboards, or scraped
pages where the useful data is the first table. Asking a model to transcribe
that table is unreliable: cells can shift, entities can stay encoded, and large
tables can overflow the run log. This tool extracts one bounded HTML table via
the standard-library :class:`html.parser.HTMLParser` and renders it as markdown
or CSV. It never executes code and never makes a network request.

The default ``TOOL:html_table:<html>`` path extracts the first table as
GitHub-flavored markdown. A single text payload can append options after
``<<<HTML_TABLE>>>`` for decision-engine use, while programmatic callers may
pass ``table_index``/``index`` and ``format`` as separate arguments.
"""

from __future__ import annotations

import csv
import io
import re
from html.parser import HTMLParser
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_OUTPUT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 200
_MAX_COLUMNS: Final[int] = 32
_DEFAULT_TABLE_INDEX: Final[int] = 1
_DEFAULT_FORMAT: Final[str] = "markdown"
_SPLIT_SENTINEL: Final[str] = "<<<HTML_TABLE>>>"
_REJECTED_TAGS: Final[frozenset[str]] = frozenset({"script", "style"})
_CELL_TAGS: Final[frozenset[str]] = frozenset({"td", "th"})
_EMBEDDED_OPTION_KEYS: Final[frozenset[str]] = frozenset({"format", "index", "table_index"})
_HORIZONTAL_WHITESPACE: Final[re.Pattern[str]] = re.compile(r"[ \t\f\v]+")
_MULTI_NEWLINE: Final[re.Pattern[str]] = re.compile(r"\n{3,}")


class _TableExtractor(HTMLParser):
    """Extract one table from an HTML document in document order."""

    def __init__(self, target_index: int) -> None:
        super().__init__(convert_charrefs=True)
        self.target_index = target_index
        self.table_count = 0
        self.rows: list[list[str]] = []
        self.rejected_tag: str | None = None
        self._rejected_depth = 0
        self._table_depth = 0
        self._selected_depth: int | None = None
        self._selected_closed = False
        self._current_row: list[str] | None = None
        self._current_cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Process an opening tag.

        Args:
            tag: Element tag name.
            attrs: Attribute pairs (unused; kept for the ``HTMLParser`` API).
        """

        del attrs
        name = tag.lower()
        if name in _REJECTED_TAGS:
            self.rejected_tag = self.rejected_tag or name
            self._rejected_depth += 1
            return
        if self._rejected_depth:
            return

        if name == "table":
            self.table_count += 1
            self._table_depth += 1
            if self.table_count == self.target_index and not self._selected_closed:
                self._selected_depth = self._table_depth
            return

        if not self._is_inside_selected_table():
            return

        if name == "tr":
            self._finish_cell()
            self._finish_row()
            self._current_row = []
            return

        if name in _CELL_TAGS:
            if self._current_row is None:
                self._current_row = []
            self._finish_cell()
            self._current_cell_parts = []
            return

        if name == "br" and self._current_cell_parts is not None:
            self._current_cell_parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle XHTML-style self-closing tags such as ``<br />``."""

        self.handle_starttag(tag, attrs)
        if tag.lower() not in {"br"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        """Process a closing tag."""

        name = tag.lower()
        if name in _REJECTED_TAGS and self._rejected_depth:
            self._rejected_depth -= 1
            return
        if self._rejected_depth:
            return

        if name == "table":
            if self._selected_depth is not None and self._table_depth == self._selected_depth:
                self._finish_cell()
                self._finish_row()
                self._selected_closed = True
                self._selected_depth = None
            if self._table_depth:
                self._table_depth -= 1
            return

        if not self._is_inside_selected_table():
            return

        if name in _CELL_TAGS:
            self._finish_cell()
            return
        if name == "tr":
            self._finish_cell()
            self._finish_row()

    def handle_data(self, data: str) -> None:
        """Append cell text when the parser is inside the selected table."""

        if self._rejected_depth or not self._is_inside_selected_table():
            return
        if self._current_cell_parts is not None and data:
            self._current_cell_parts.append(data)

    def close(self) -> None:
        """Finalize a still-open selected table before returning rows."""

        super().close()
        if self._selected_depth is not None:
            self._finish_cell()
            self._finish_row()
            self._selected_closed = True
            self._selected_depth = None

    def _is_inside_selected_table(self) -> bool:
        """Return whether events belong to the selected table itself."""

        return self._selected_depth is not None and self._table_depth == self._selected_depth

    def _finish_cell(self) -> None:
        """Close the current cell, if any."""

        if self._current_cell_parts is None:
            return
        if self._current_row is None:
            self._current_row = []
        self._current_row.append(_normalize_cell("".join(self._current_cell_parts)))
        self._current_cell_parts = None

    def _finish_row(self) -> None:
        """Close the current row, if it contains cells."""

        if self._current_row is None:
            return
        if self._current_row:
            self.rows.append(self._current_row)
        self._current_row = None


class HtmlTableTool:
    """Extract a bounded HTML table as markdown or CSV."""

    name = "html_table"
    description = (
        "Extracts the first HTML table (or 1-based table_index) and renders it as markdown or CSV; "
        "caps document chars, output chars, rows, and columns."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Extract an HTML table from invocation arguments.

        Args:
            invocation: Tool invocation whose ``text``/``html`` argument holds
                the HTML document. Optional ``table_index``/``index`` selects a
                1-based table number, and ``format`` may be ``markdown`` or
                ``csv``. A single text payload may append options after
                ``<<<HTML_TABLE>>>``.

        Returns:
            Tool result whose content is the extracted table or an ``ok=False``
            structured failure for empty, oversized, missing, malformed option,
            out-of-bounds, or too-large table requests.
        """

        document, options, resolve_error = self._resolve_options(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None

        if not document.strip():
            return self._fail("document is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        table_index = self._parse_table_index(options.get("table_index", options.get("index", _DEFAULT_TABLE_INDEX)))
        if table_index is None:
            return self._fail(
                "table_index must be a positive 1-based integer",
                {"table_index": str(options.get("table_index", options.get("index", _DEFAULT_TABLE_INDEX)))},
            )

        output_format = str(options.get("format", _DEFAULT_FORMAT)).strip().lower()
        if output_format == "md":
            output_format = "markdown"
        if output_format not in {"markdown", "csv"}:
            return self._fail(
                "format must be 'markdown' or 'csv'",
                {"format": str(options.get("format", _DEFAULT_FORMAT))},
            )

        parser = _TableExtractor(table_index)
        try:
            parser.feed(document)
            parser.close()
        except (AssertionError, TypeError, ValueError) as exc:
            return self._fail(f"could not parse HTML: {exc}", {})

        if parser.rejected_tag is not None:
            return self._fail(
                f"document contains rejected <{parser.rejected_tag}> content",
                {"rejected_tag": parser.rejected_tag},
            )
        if parser.table_count == 0:
            return self._fail("document contains no table", {"table_count": 0})
        if table_index > parser.table_count:
            return self._fail(
                "table_index is out of bounds",
                {"table_index": table_index, "table_count": parser.table_count},
            )

        rows = parser.rows
        if not rows:
            return self._fail(
                "table has no rows",
                {"table_index": table_index, "table_count": parser.table_count},
            )

        width = max(len(row) for row in rows)
        if width == 0:
            return self._fail(
                "table has no columns",
                {"table_index": table_index, "table_count": parser.table_count},
            )
        if len(rows) > _MAX_ROWS:
            return self._fail(
                f"row count exceeds max_rows={_MAX_ROWS}",
                {"rows": len(rows), "table_index": table_index, "table_count": parser.table_count},
            )
        if width > _MAX_COLUMNS:
            return self._fail(
                f"column count exceeds max_columns={_MAX_COLUMNS}",
                {"columns": width, "table_index": table_index, "table_count": parser.table_count},
            )

        padded_rows = [row + [""] * (width - len(row)) for row in rows]
        content = self._render_csv(padded_rows) if output_format == "csv" else self._render_markdown(padded_rows)
        if len(content) > _MAX_OUTPUT_CHARS:
            return self._fail(
                f"output exceeds max_chars={_MAX_OUTPUT_CHARS}",
                {
                    "chars": len(content),
                    "table_index": table_index,
                    "table_count": parser.table_count,
                },
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "table_index": table_index,
                "table_count": parser.table_count,
                "row_count": len(padded_rows),
                "column_count": width,
                "format": output_format,
                "source_chars": len(document),
                "chars": len(content),
            },
        )

    @classmethod
    def _resolve_options(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, dict[str, object], str | None]:
        """Resolve HTML text and options from separate args or sentinel text."""

        document = str(arguments.get("text", arguments.get("html", "")))
        options = {key: value for key, value in arguments.items() if key not in {"text", "html"}}
        if _SPLIT_SENTINEL not in document:
            return document, options, None

        html_document, embedded_options = document.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in embedded_options:
            return None, {}, "text contains more than one <<<HTML_TABLE>>> sentinel"

        parsed_options, error = cls._parse_embedded_options(embedded_options)
        if error is not None:
            return None, {}, error

        merged_options: dict[str, object] = dict(parsed_options)
        merged_options.update(options)
        return html_document.strip("\n"), merged_options, None

    @classmethod
    def _parse_embedded_options(cls, raw_options: str) -> tuple[dict[str, str], str | None]:
        """Parse ``key=value`` options from a sentinel payload."""

        option_text = raw_options.strip()
        if not option_text:
            return {}, None

        raw_parts = option_text.splitlines() if "\n" in option_text else option_text.split(";")
        parsed: dict[str, str] = {}
        for raw_part in raw_parts:
            part = raw_part.strip()
            if not part:
                continue
            if "=" not in part:
                return {}, f"html_table option must be key=value, got {part!r}"
            key, value = part.split("=", maxsplit=1)
            key = key.strip()
            value = value.strip()
            if key not in _EMBEDDED_OPTION_KEYS:
                return {}, f"unsupported html_table option: {key}"
            parsed[key] = value
        return parsed, None

    @staticmethod
    def _parse_table_index(value: object) -> int | None:
        """Parse a positive 1-based table index while rejecting booleans."""

        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value >= 1 else None
        if isinstance(value, str):
            text = value.strip()
            if text.isdecimal():
                parsed = int(text)
                return parsed if parsed >= 1 else None
        return None

    @staticmethod
    def _render_markdown(rows: list[list[str]]) -> str:
        """Render padded rows as a GitHub-flavored markdown table."""

        header = rows[0]
        body = rows[1:]
        lines = [
            HtmlTableTool._format_markdown_row(header),
            HtmlTableTool._format_markdown_row(["---"] * len(header)),
        ]
        lines.extend(HtmlTableTool._format_markdown_row(row) for row in body)
        return "\n".join(lines)

    @staticmethod
    def _format_markdown_row(row: list[str]) -> str:
        """Format one markdown table row."""

        return "| " + " | ".join(HtmlTableTool._escape_markdown_cell(cell) for cell in row) + " |"

    @staticmethod
    def _escape_markdown_cell(cell: str) -> str:
        """Escape cell content that would otherwise break a pipe table."""

        return cell.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")

    @staticmethod
    def _render_csv(rows: list[list[str]]) -> str:
        """Render padded rows as CSV."""

        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerows(rows)
        return output.getvalue().rstrip("\n")

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _normalize_cell(text: str) -> str:
    """Normalize HTML cell text without inventing content."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _HORIZONTAL_WHITESPACE.sub(" ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    normalized = _MULTI_NEWLINE.sub("\n\n", normalized)
    return normalized.strip()
