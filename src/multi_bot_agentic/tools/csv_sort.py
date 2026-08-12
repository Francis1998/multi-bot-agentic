"""Deterministic CSV row-sorting tool.

Agents often need CSV rows ordered by a named column before the next LLM turn.
Asking a model to sort pasted tables can drop quoted cells or scramble headers.
This tool uses stdlib :mod:`csv` only, keeps the header row, and sorts data
rows by a required column with optional descending and numeric modes. It never
executes code and never makes network requests. Safe for GPT-5.5 / Claude
Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:csv_sort:<payload>``, the CSV document and column may be supplied either
as separate ``text`` / ``column`` arguments or as a single ``text`` value split
on ``<<<CSV_SORT>>>``.
"""

from __future__ import annotations

import csv
import io
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64
_DEFAULT_DESCENDING: Final[bool] = False
_DEFAULT_NUMERIC: Final[bool] = False
_SPLIT_SENTINEL: Final[str] = "<<<CSV_SORT>>>"
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


class CsvSortTool:
    """Sort CSV rows by a named column while preserving the header."""

    name = "csv_sort"
    description = (
        "Sorts CSV rows by a named column (optional descending/numeric); "
        "accepts text+column or <<<CSV_SORT>>>; max 500 rows, 64 columns."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Sort a CSV document by one named column."""

        document, column, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and column is not None

        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )
        if not column:
            return self._fail("column name is required", {})

        descending, desc_error = self._resolve_bool(
            invocation.arguments,
            "descending",
            _DEFAULT_DESCENDING,
        )
        if desc_error is not None:
            return self._fail(desc_error, {})
        assert descending is not None

        numeric, numeric_error = self._resolve_bool(
            invocation.arguments,
            "numeric",
            _DEFAULT_NUMERIC,
        )
        if numeric_error is not None:
            return self._fail(numeric_error, {})
        assert numeric is not None

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
        if column not in header_names:
            return self._fail(
                f"unknown column: {column!r}",
                {"columns": ",".join(header_names)},
            )

        index = header_names.index(column)
        data_rows: list[list[str]] = []
        for row_number, row in enumerate(rows[1:], start=2):
            if self._is_blank_row(row):
                continue
            if len(row) != len(header_names):
                return self._fail(
                    f"csv row {row_number} has {len(row)} columns; expected {len(header_names)}",
                    {"column": column},
                )
            data_rows.append(list(row))

        if numeric:
            numeric_rows: list[list[str]] = []
            non_numeric_rows: list[list[str]] = []
            for row in data_rows:
                try:
                    float(row[index])
                except ValueError:
                    non_numeric_rows.append(row)
                else:
                    numeric_rows.append(row)
            sorted_rows = sorted(
                numeric_rows,
                key=lambda row: float(row[index]),
                reverse=descending,
            ) + sorted(
                non_numeric_rows,
                key=lambda row: row[index],
                reverse=descending,
            )
        else:
            sorted_rows = sorted(data_rows, key=lambda row: row[index], reverse=descending)
        content = self._dump_csv([header_names, *sorted_rows])
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "rows": len(sorted_rows),
                "columns": len(header_names),
                "column": column,
                "descending": descending,
                "numeric": numeric,
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, str | None, str | None]:
        """Resolve CSV document and column name from args or a sentinel payload."""

        text = str(arguments.get("text", ""))
        if "column" in arguments:
            column = str(arguments["column"]).strip()
            return text, column, None

        if _SPLIT_SENTINEL not in text:
            return (
                None,
                None,
                f"csv_sort requires text+column arguments, or a single text split on {_SPLIT_SENTINEL!r}",
            )

        if text.count(_SPLIT_SENTINEL) != 1:
            return None, None, "text contains more than one <<<CSV_SORT>>> sentinel"
        document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
        column = remainder.strip()
        if not column:
            return None, None, "column name is required"
        return document, column, None

    @classmethod
    def _resolve_bool(
        cls,
        arguments: dict[str, object],
        name: str,
        default: bool,
    ) -> tuple[bool | None, str | None]:
        """Resolve an optional boolean argument with a default."""

        if name not in arguments:
            return default, None
        parsed = cls._parse_bool(arguments[name])
        if parsed is None:
            return None, f"{name} must be a boolean, got {arguments[name]!r}"
        return parsed, None

    @staticmethod
    def _parse_bool(value: object) -> bool | None:
        """Coerce a boolean-like argument."""

        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in _TRUTHY:
                return True
            if normalized in _FALSY:
                return False
        return None

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
