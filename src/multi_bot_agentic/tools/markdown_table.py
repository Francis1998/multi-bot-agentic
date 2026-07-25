"""Deterministic GitHub-flavored markdown table renderer.

Agent runs often need to turn a small tabular observation into a markdown table
for a final answer, issue comment, or audit note. Asking a language model to
format the table is unreliable (broken pipes, shifted columns, unbounded rows).
This tool converts CSV-like text or explicit list-of-rows input into a bounded
GitHub-flavored markdown table. It never executes code and never makes a network
request, matching the ``csv``, ``truncate``, ``diff``, and ``regex`` tool
contracts.

Because the decision engine forwards a single ``text`` payload from
``TOOL:markdown_table:<payload>``, text input is parsed as CSV by default. If the
text payload is a JSON array of rows, it is parsed as data instead. Programmatic
callers may pass ``rows`` directly.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 200
_MAX_COLUMNS: Final[int] = 32
_DEFAULT_DELIMITER: Final[str] = ","


class MarkdownTableTool:
    """Render a bounded table as GitHub-flavored markdown."""

    name = "markdown_table"
    description = (
        "Converts CSV-like text or list-of-rows input into a GitHub-flavored markdown table; "
        "caps rows/columns; optional delimiter."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Render tabular input from the invocation arguments.

        Args:
            invocation: Tool invocation whose ``text`` argument holds CSV-like
                text or a JSON array of rows, or whose ``rows`` argument holds an
                explicit list of rows. Optional ``delimiter`` overrides the
                default ``,`` field separator for CSV text input.

        Returns:
            Tool result whose ``content`` is a markdown table string, or
            ``ok=False`` and an explanation when input is empty/oversized,
            malformed, or exceeds the row/column caps.
        """

        raw_rows, input_type, delimiter, error, metadata = self._resolve_rows(invocation.arguments)
        if error is not None:
            return self._fail(error, metadata)

        assert raw_rows is not None
        if not raw_rows:
            return self._fail("table has no rows", {"input_type": input_type})

        width = max(len(row) for row in raw_rows)
        if width == 0:
            return self._fail("table has no columns", {"input_type": input_type})
        if width > _MAX_COLUMNS:
            return self._fail(
                f"column count exceeds max_columns={_MAX_COLUMNS}",
                {"columns": width, "input_type": input_type},
            )
        if len(raw_rows) > _MAX_ROWS + 1:
            # +1 accounts for the header row.
            return self._fail(
                f"row count exceeds max_rows={_MAX_ROWS} (excluding header)",
                {"rows": len(raw_rows) - 1, "input_type": input_type},
            )

        padded_rows = [row + [""] * (width - len(row)) for row in raw_rows]
        markdown = self._render_markdown(padded_rows)
        payload: dict[str, object] = {
            "row_count": len(padded_rows) - 1,
            "column_count": width,
            "input_type": input_type,
        }
        if delimiter is not None:
            payload["delimiter"] = delimiter

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=markdown,
            metadata=payload,
        )

    def _resolve_rows(
        self,
        arguments: dict[str, object],
    ) -> tuple[list[list[str]] | None, str, str | None, str | None, dict[str, object]]:
        """Resolve rows from either ``rows`` or ``text`` arguments.

        Args:
            arguments: Tool invocation arguments.

        Returns:
            ``(rows, input_type, delimiter, error, metadata)``.
        """

        if "rows" in arguments:
            rows, error, metadata = self._coerce_rows(arguments.get("rows"), input_type="rows")
            return rows, "rows", None, error, metadata

        document = str(arguments.get("text", ""))
        if not document.strip():
            return None, "csv", None, "document is empty", {}
        if len(document) > _MAX_DOCUMENT_CHARS:
            return None, "csv", None, f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}", {"chars": len(document)}

        stripped = document.lstrip()
        if stripped.startswith("["):
            parsed_rows, error, metadata = self._coerce_json_rows(document)
            if parsed_rows is not None or error is not None:
                return parsed_rows, "json_rows", None, error, metadata

        delimiter = str(arguments.get("delimiter", _DEFAULT_DELIMITER))
        if len(delimiter) != 1:
            return (
                None,
                "csv",
                delimiter,
                f"delimiter must be a single character, got {delimiter!r}",
                {"delimiter": delimiter},
            )

        try:
            reader = csv.reader(io.StringIO(document), delimiter=delimiter)
            rows = [list(row) for row in reader]
        except csv.Error as exc:
            return None, "csv", delimiter, f"invalid CSV: {exc}", {}

        # Drop bare trailing empty rows produced by trailing newlines.
        while rows and len(rows[-1]) == 1 and rows[-1][0] == "":
            rows.pop()

        return rows, "csv", delimiter, None, {}

    def _coerce_json_rows(self, document: str) -> tuple[list[list[str]] | None, str | None, dict[str, object]]:
        """Parse and coerce a JSON list-of-rows document.

        Args:
            document: Raw text document.

        Returns:
            ``(rows, error, metadata)``. Invalid JSON falls back to CSV parsing
            by returning ``(None, None, {})``.
        """

        try:
            value = json.loads(document)
        except json.JSONDecodeError:
            return None, None, {}
        return self._coerce_rows(value, input_type="json_rows")

    def _coerce_rows(
        self,
        value: object,
        input_type: str,
    ) -> tuple[list[list[str]] | None, str | None, dict[str, object]]:
        """Coerce explicit row input into strings.

        Args:
            value: Raw row collection.
            input_type: Metadata label for the input source.

        Returns:
            ``(rows, error, metadata)``.
        """

        if not isinstance(value, (list, tuple)):
            return None, "rows must be a list of row lists", {"input_type": input_type}

        rows: list[list[str]] = []
        total_chars = 0
        for row_index, row in enumerate(value):
            if isinstance(row, str) or not isinstance(row, (list, tuple)):
                return None, f"row {row_index} must be a list of cells", {"input_type": input_type}
            coerced_row = ["" if cell is None else str(cell) for cell in row]
            total_chars += sum(len(cell) for cell in coerced_row)
            rows.append(coerced_row)

        if total_chars > _MAX_DOCUMENT_CHARS:
            return (
                None,
                f"rows exceed max_chars={_MAX_DOCUMENT_CHARS}",
                {
                    "chars": total_chars,
                    "input_type": input_type,
                },
            )
        return rows, None, {}

    @staticmethod
    def _render_markdown(rows: list[list[str]]) -> str:
        """Render padded rows as a markdown table.

        Args:
            rows: Non-empty, rectangular table rows.

        Returns:
            GitHub-flavored markdown table.
        """

        header = rows[0]
        body = rows[1:]
        separator = ["---"] * len(header)
        lines = [
            MarkdownTableTool._format_row(header),
            MarkdownTableTool._format_row(separator),
        ]
        lines.extend(MarkdownTableTool._format_row(row) for row in body)
        return "\n".join(lines)

    @staticmethod
    def _format_row(row: list[str]) -> str:
        """Format one markdown table row."""

        return "| " + " | ".join(MarkdownTableTool._escape_cell(cell) for cell in row) + " |"

    @staticmethod
    def _escape_cell(cell: str) -> str:
        """Escape cell content that would otherwise break a pipe table."""

        normalized = cell.replace("\r\n", "\n").replace("\r", "\n")
        return normalized.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result.

        Args:
            message: Human-readable failure explanation.
            metadata: Structured metadata for the failure.

        Returns:
            A ``ok=False`` tool result carrying the message and metadata.
        """

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
