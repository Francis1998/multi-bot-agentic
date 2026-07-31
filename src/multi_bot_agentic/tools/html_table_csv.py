"""Deterministic HTML table-to-CSV conversion tool.

Agent runs often receive HTML with one or more data tables. Asking a model to
transcribe those tables into CSV is unreliable: cells shift, entities stay
encoded, and large tables overflow the event log. This tool converts the first
table or every ``<table>`` in a bounded HTML fragment to CSV text via the
standard-library :class:`html.parser.HTMLParser`, reusing the extraction
patterns from ``html_table``. It rejects documents containing ``script`` or
``style``, never executes code, and never makes a network request — safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
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
_REJECTED_TAGS: Final[frozenset[str]] = frozenset({"script", "style"})
_CELL_TAGS: Final[frozenset[str]] = frozenset({"td", "th"})
_HORIZONTAL_WHITESPACE: Final[re.Pattern[str]] = re.compile(r"[ \t\f\v]+")
_MULTI_NEWLINE: Final[re.Pattern[str]] = re.compile(r"\n{3,}")


class _TableExtractor(HTMLParser):
    """Extract one or all tables from an HTML document in document order."""

    def __init__(self, *, all_tables: bool, target_index: int = 1) -> None:
        super().__init__(convert_charrefs=True)
        self.all_tables = all_tables
        self.target_index = target_index
        self.table_count = 0
        self.tables: list[list[list[str]]] = []
        self.rows: list[list[str]] = []
        self.rejected_tag: str | None = None
        self._rejected_depth = 0
        self._table_depth = 0
        self._selected_depth: int | None = None
        self._selected_closed = False
        self._current_row: list[str] | None = None
        self._current_cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Process an opening tag."""

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
            if self.all_tables:
                self._finish_table()
                self._selected_depth = self._table_depth
                self._selected_closed = False
                self.rows = []
            elif self.table_count == self.target_index and not self._selected_closed:
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
                if self.all_tables:
                    self._finish_table()
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
        """Append cell text when inside the selected table."""

        if self._rejected_depth or not self._is_inside_selected_table():
            return
        if self._current_cell_parts is not None and data:
            self._current_cell_parts.append(data)

    def close(self) -> None:
        """Finalize any still-open selected table."""

        super().close()
        if self._selected_depth is not None:
            self._finish_cell()
            self._finish_row()
            if self.all_tables:
                self._finish_table()
            self._selected_closed = True
            self._selected_depth = None

    def _is_inside_selected_table(self) -> bool:
        """Return whether events belong to the selected table."""

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
        """Close the current row when it contains cells."""

        if self._current_row is None:
            return
        if self._current_row:
            self.rows.append(self._current_row)
        self._current_row = None

    def _finish_table(self) -> None:
        """Store the current table rows when collecting all tables."""

        if self.rows:
            self.tables.append(self.rows)
        self.rows = []


class HtmlTableCsvTool:
    """Convert the first or all HTML tables in a document to CSV text."""

    name = "html_table_csv"
    description = (
        "Converts the first HTML table (default) or all tables (all=true) to CSV text; "
        "rejects script/style; empty/oversized → ok=False."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Convert HTML tables in the invocation to CSV.

        Args:
            invocation: Tool invocation whose ``text``/``html`` argument holds the
                HTML document. Optional ``all`` (bool) selects every table instead
                of only the first.

        Returns:
            Tool result whose ``content`` is CSV text, or ``ok=False`` and an
            explanation when the document is empty, too long, contains rejected
            tags, has no tables, or the CSV output exceeds the character cap.
        """

        document = str(invocation.arguments.get("text", invocation.arguments.get("html", "")))
        all_tables = _parse_bool(invocation.arguments.get("all", False))

        if not document.strip():
            return self._fail("document is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        parser = _TableExtractor(all_tables=all_tables, target_index=1)
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

        table_sets = parser.tables if all_tables else ([parser.rows] if parser.rows else [])
        if not table_sets:
            return self._fail(
                "table has no rows",
                {"table_count": parser.table_count, "all": all_tables},
            )

        csv_blocks = [self._render_csv(_pad_rows(rows)) for rows in table_sets if rows]
        if not csv_blocks:
            return self._fail(
                "table has no rows",
                {"table_count": parser.table_count, "all": all_tables},
            )

        content = "\n\n".join(csv_blocks)
        if len(content) > _MAX_OUTPUT_CHARS:
            return self._fail(
                f"output exceeds max_chars={_MAX_OUTPUT_CHARS}",
                {"chars": len(content), "table_count": parser.table_count, "all": all_tables},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "all": all_tables,
                "table_count": parser.table_count,
                "tables_rendered": len(csv_blocks),
                "source_chars": len(document),
                "chars": len(content),
            },
        )

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


def _parse_bool(value: object) -> bool:
    """Parse a boolean flag while rejecting ambiguous truthy strings."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def _pad_rows(rows: list[list[str]]) -> list[list[str]]:
    """Pad ragged rows to a rectangular grid."""

    width = max(len(row) for row in rows)
    return [row + [""] * (width - len(row)) for row in rows]


def _normalize_cell(text: str) -> str:
    """Normalize HTML cell text without inventing content."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _HORIZONTAL_WHITESPACE.sub(" ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    normalized = _MULTI_NEWLINE.sub("\n\n", normalized)
    return normalized.strip()
