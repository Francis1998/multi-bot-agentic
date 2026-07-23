"""Deterministic CSV parsing tool.

Agent runs routinely ingest tabular snippets: a small export pasted into a goal,
a tool payload that is comma-separated, or a checklist rendered as CSV. Asking a
language model to invent row/column structure is unreliable (shifted columns,
dropped quotes, inconsistent types). This tool parses CSV text via the stdlib
``csv`` module into canonical JSON (header + rows), with bounded document size
and hard caps on row and column counts. It never executes code and never makes a
network request, matching the ``diff``, ``duration``, ``hash``, ``slugify``, and
``json_format`` tool contracts.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:csv:<payload>``, the CSV document is the ``text`` argument. Optional
``delimiter`` may be supplied by programmatic callers (default ``,``).
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


class CsvParseTool:
    """Parse a CSV document into canonical JSON with row/column caps."""

    name = "csv"
    description = "Parses CSV text into JSON (header + rows); caps rows/columns; optional delimiter."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse the CSV document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the CSV
                document and whose optional ``delimiter`` argument overrides the
                default ``,`` field separator (must be a single character).

        Returns:
            Tool result whose ``content`` is canonical JSON with ``header``,
            ``rows``, and counts, or ``ok=False`` and an explanation when the
            document is empty/oversized, the delimiter is invalid, or the
            table exceeds the row/column caps.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document.strip():
            return self._fail("document is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        delimiter = str(invocation.arguments.get("delimiter", _DEFAULT_DELIMITER))
        if len(delimiter) != 1:
            return self._fail(
                f"delimiter must be a single character, got {delimiter!r}",
                {"delimiter": delimiter},
            )

        try:
            reader = csv.reader(io.StringIO(document), delimiter=delimiter)
            raw_rows = [list(row) for row in reader]
        except csv.Error as exc:
            return self._fail(f"invalid CSV: {exc}", {})

        # Drop a single trailing empty row that bare trailing newlines produce.
        while raw_rows and len(raw_rows[-1]) == 1 and raw_rows[-1][0] == "":
            raw_rows.pop()

        if not raw_rows:
            return self._fail("document has no rows", {})

        width = max(len(row) for row in raw_rows)
        if width > _MAX_COLUMNS:
            return self._fail(
                f"column count exceeds max_columns={_MAX_COLUMNS}",
                {"columns": width},
            )
        if len(raw_rows) > _MAX_ROWS + 1:
            # +1 accounts for the header row.
            return self._fail(
                f"row count exceeds max_rows={_MAX_ROWS} (excluding header)",
                {"rows": len(raw_rows) - 1},
            )

        header = list(raw_rows[0])
        # Pad short header / body rows so every row has ``width`` cells.
        header.extend([""] * (width - len(header)))
        blank_header_columns = [index for index, name in enumerate(header) if not name.strip()]
        if blank_header_columns:
            return self._fail(
                "header contains blank column names",
                {"columns": blank_header_columns},
            )
        body: list[list[str]] = []
        for row in raw_rows[1:]:
            padded = list(row) + [""] * (width - len(row))
            body.append(padded)

        # If the first row looks like data (no header names), still treat it as
        # the header — callers that want synthetic headers can prepend them.
        payload: dict[str, object] = {
            "header": header,
            "rows": body,
            "row_count": len(body),
            "column_count": width,
            "delimiter": delimiter,
        }
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
            metadata={
                "row_count": len(body),
                "column_count": width,
                "delimiter": delimiter,
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result.

        Args:
            message: Human-readable failure explanation.
            metadata: Structured metadata for the failure.

        Returns:
            A ``ok=False`` tool result carrying the message and metadata.
        """

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
