"""Deterministic CSV row-deduplication tool.

Agents often need CSV rows unique on one or more named columns before the next
LLM turn. Asking a model to drop duplicates can remove the wrong row or scramble
quoted cells. This tool uses stdlib :mod:`csv` only, keeps the header, and
retains the first occurrence of each key. It never executes code and never makes
network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
workers.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:csv_unique:<payload>``, the CSV document and column list may be supplied
either as separate ``text`` / ``columns`` arguments or as a single ``text``
value split on ``<<<CSV_UNIQUE>>>``.
"""

from __future__ import annotations

import csv
import io
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64
_SPLIT_SENTINEL: Final[str] = "<<<CSV_UNIQUE>>>"


class CsvUniqueTool:
    """Deduplicate CSV rows by named column(s), keeping the first occurrence."""

    name = "csv_unique"
    description = (
        "Deduplicates CSV rows by named column(s), keeping first occurrence; "
        "accepts text+columns or <<<CSV_UNIQUE>>>; max 500 rows, 64 columns."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Deduplicate a CSV document by one or more named columns."""

        document, columns, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and columns is not None

        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )
        if not columns:
            return self._fail("columns list is empty", {})
        if any(not name for name in columns):
            return self._fail("column names must be non-empty", {"columns": ",".join(columns)})
        if len(set(columns)) != len(columns):
            return self._fail("requested columns must be unique", {"columns": ",".join(columns)})
        if len(columns) > _MAX_COLUMNS:
            return self._fail(
                f"requested columns exceed max_columns={_MAX_COLUMNS}",
                {"columns": len(columns)},
            )

        try:
            rows = list(csv.reader(io.StringIO(document)))
        except csv.Error as exc:
            return self._fail(f"csv parse error: {exc}", {})

        while rows and self._is_blank_row(rows[-1]):
            rows.pop()

        if not rows or not any(cell.strip() for row in rows for cell in row):
            return self._fail("csv has no rows", {})
        if len(rows) > _MAX_ROWS + 1:
            return self._fail(
                f"csv exceeds max_rows={_MAX_ROWS}",
                {"rows": len(rows) - 1},
            )

        width = max(len(row) for row in rows)
        if width > _MAX_COLUMNS:
            return self._fail(
                f"csv exceeds max_columns={_MAX_COLUMNS}",
                {"columns": width},
            )

        header = list(rows[0]) + [""] * (width - len(rows[0]))
        header_names = [cell.strip() for cell in header]
        if not header_names or any(not name for name in header_names):
            return self._fail("csv header must be non-empty named columns", {})
        if len(set(header_names)) != len(header_names):
            return self._fail("csv header columns must be unique", {})

        missing = [name for name in columns if name not in header_names]
        if missing:
            return self._fail(
                f"unknown column: {missing[0]!r}",
                {"columns": ",".join(header_names), "missing": ",".join(missing)},
            )

        indexes = [header_names.index(name) for name in columns]
        seen: set[tuple[str, ...]] = set()
        unique_rows: list[list[str]] = []
        dropped = 0
        for row_number, row in enumerate(rows[1:], start=2):
            if self._is_blank_row(row):
                continue
            if len(row) != len(header_names):
                return self._fail(
                    f"csv row {row_number} has {len(row)} columns; expected {len(header_names)}",
                    {"columns": ",".join(columns)},
                )
            key = tuple(row[index] for index in indexes)
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
            unique_rows.append(list(row))

        content = self._dump_csv([header_names, *unique_rows])
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "rows": len(unique_rows),
                "columns": len(header_names),
                "key_columns": ",".join(columns),
                "dropped": dropped,
                "chars": len(content),
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, list[str] | None, str | None]:
        """Resolve CSV document and column names from args or a sentinel payload."""

        text = str(arguments.get("text", ""))
        if "columns" in arguments:
            columns, error = cls._parse_columns(arguments["columns"])
            if error is not None:
                return None, None, error
            return text, columns, None

        if _SPLIT_SENTINEL not in text:
            return (
                None,
                None,
                (f"csv_unique requires text+columns arguments, or a single text split on {_SPLIT_SENTINEL!r}"),
            )

        if text.count(_SPLIT_SENTINEL) != 1:
            return None, None, "text contains more than one <<<CSV_UNIQUE>>> sentinel"
        document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
        columns, error = cls._parse_columns(remainder.strip("\n"))
        if error is not None:
            return None, None, error
        return document, columns, None

    @staticmethod
    def _parse_columns(raw: object) -> tuple[list[str] | None, str | None]:
        """Parse a columns argument into a list of stripped names."""

        if isinstance(raw, (list, tuple)):
            names = [str(item).strip() for item in raw]
            return names, None
        text = str(raw).strip()
        if not text:
            return None, "columns list is empty"
        if "\n" in text and "," not in text:
            names = [line.strip() for line in text.splitlines() if line.strip()]
        else:
            names = [part.strip() for part in text.split(",")]
        return names, None

    @staticmethod
    def _is_blank_row(row: list[str]) -> bool:
        """Return whether a parsed row has no non-whitespace cells."""

        return not row or all(not cell.strip() for cell in row)

    @staticmethod
    def _dump_csv(rows: list[list[str]]) -> str:
        """Serialize rows to CSV text with a trailing newline."""

        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerows(rows)
        return buffer.getvalue()

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
