"""CSV-to-JSON array-of-objects tool for agent tabular handoffs.

Agent runs routinely convert small CSV exports into JSON records for the next
tool or model turn. Asking a language model to invent object keys from a header
row is unreliable (shifted columns, dropped quotes). This tool parses CSV text
via the stdlib ``csv`` module into a JSON array of objects keyed by the header
row, with bounded document size and hard caps on row and column counts. It
never executes code and never makes network requests. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64
_DEFAULT_DELIMITER: Final[str] = ","


class CsvToJsonTool:
    """Parse CSV text into a JSON array of objects (header row required)."""

    name = "csv_to_json"
    description = (
        "Parses CSV text into a JSON array of objects keyed by the header row; "
        "optional delimiter; caps rows/columns; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse the CSV document into a JSON array of objects.

        Args:
            invocation: Tool invocation whose ``csv`` (or ``text``) argument
                holds the CSV document and whose optional ``delimiter`` argument
                overrides the default ``,`` field separator (must be a single
                character). A non-empty header row is required.

        Returns:
            Tool result whose ``content`` is pretty JSON (array of objects), or
            ``ok=False`` when the document is empty/oversized, the delimiter is
            invalid, the header is missing/blank, or the table exceeds caps.
        """

        raw = invocation.arguments.get("csv")
        if raw is None:
            raw = invocation.arguments.get("text")
        if raw is None:
            return self._fail("missing required argument: csv", {})
        document = str(raw)
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

        header = [cell.strip() for cell in raw_rows[0]]
        if not header or any(not name for name in header):
            return self._fail("header row is required and must be non-blank", {"header": header})

        if len(header) != len(set(header)):
            return self._fail("header columns must be unique", {"header": header})

        if len(header) > _MAX_COLUMNS:
            return self._fail(
                f"column count exceeds max_columns={_MAX_COLUMNS}",
                {"columns": len(header)},
            )

        body = raw_rows[1:]
        if len(body) > _MAX_ROWS:
            return self._fail(
                f"row count exceeds max_rows={_MAX_ROWS}",
                {"rows": len(body)},
            )

        records: list[dict[str, str]] = []
        for row_index, row in enumerate(body, start=1):
            if len(row) > len(header):
                return self._fail(
                    f"row {row_index} has more columns than the header",
                    {"row": row_index, "columns": len(row), "header_columns": len(header)},
                )
            # Pad short rows with empty strings so every object has all keys.
            padded = list(row) + [""] * (len(header) - len(row))
            records.append({header[i]: padded[i] for i in range(len(header))})

        content = json.dumps(records, indent=2, ensure_ascii=False)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "rows": len(records),
                "columns": len(header),
                "header": header,
                "delimiter": delimiter,
                "chars": len(document),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
