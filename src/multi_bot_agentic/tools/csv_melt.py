"""Deterministic CSV wide-to-long melt tool.

Agents often need wide CSV observations reshaped into long form before the next
model turn. Asking a model to unpivot a table can drop identifiers or mismatch
column names and values. This tool uses stdlib :mod:`csv` only and emits fixed
``variable`` / ``value`` columns. It never executes code or makes network
requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

The CSV and identifier columns may be supplied as separate ``text`` /
``id_vars`` arguments, with optional ``value_vars``, or as a single ``text``
value split on ``<<<CSV_MELT>>>``.
"""

from __future__ import annotations

import csv
import io
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64
_SPLIT_SENTINEL: Final[str] = "<<<CSV_MELT>>>"
_VARIABLE_COLUMN: Final[str] = "variable"
_VALUE_COLUMN: Final[str] = "value"


class CsvMeltTool:
    """Unpivot wide CSV columns into fixed variable/value rows."""

    name = "csv_melt"
    description = (
        "Melts wide CSV to id_vars+variable+value rows via stdlib csv; optional value_vars "
        "or <<<CSV_MELT>>>; max 20_000 chars, 500 rows, 64 columns."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Melt a CSV document from wide to long form."""

        document, id_vars, value_vars, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and id_vars is not None

        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
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

        header = [cell.strip() for cell in rows[0]]
        if not header or any(not name for name in header):
            return self._fail("csv header must be non-empty named columns", {})
        if len(set(header)) != len(header):
            return self._fail("csv header columns must be unique", {})

        selection_error = self._validate_columns(header, id_vars, value_vars)
        if selection_error is not None:
            return self._fail(selection_error, {"columns": ",".join(header)})
        selected_values = value_vars if value_vars is not None else [name for name in header if name not in id_vars]
        if not selected_values:
            return self._fail("csv_melt requires at least one value column", {"id_vars": ",".join(id_vars)})
        output_columns = len(id_vars) + 2
        if output_columns > _MAX_COLUMNS:
            return self._fail(
                f"melt output exceeds max_columns={_MAX_COLUMNS}",
                {"columns": output_columns},
            )

        id_indexes = [header.index(name) for name in id_vars]
        value_indexes = [header.index(name) for name in selected_values]
        melted_rows: list[list[str]] = [[*id_vars, _VARIABLE_COLUMN, _VALUE_COLUMN]]
        for row_number, row in enumerate(rows[1:], start=2):
            if self._is_blank_row(row):
                continue
            if len(row) != len(header):
                return self._fail(
                    f"csv row {row_number} has {len(row)} columns; expected {len(header)}",
                    {},
                )
            id_values = [row[index] for index in id_indexes]
            for name, index in zip(selected_values, value_indexes, strict=True):
                melted_rows.append([*id_values, name, row[index]])
                if len(melted_rows) - 1 > _MAX_ROWS:
                    return self._fail(
                        f"melt output exceeds max_rows={_MAX_ROWS}",
                        {"rows": len(melted_rows) - 1},
                    )

        content = self._dump_csv(melted_rows)
        if len(content) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"melt output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(content)},
            )
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "rows": len(melted_rows) - 1,
                "columns": output_columns,
                "id_vars": ",".join(id_vars),
                "value_vars": ",".join(selected_values),
                "chars": len(content),
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, list[str] | None, list[str] | None, str | None]:
        """Resolve CSV text and column lists from arguments or sentinel syntax."""

        text = str(arguments.get("text", ""))
        if "id_vars" in arguments:
            id_vars, id_error = cls._parse_columns(arguments["id_vars"], "id_vars")
            if id_error is not None:
                return None, None, None, id_error
            value_vars: list[str] | None = None
            if "value_vars" in arguments:
                value_vars, value_error = cls._parse_columns(arguments["value_vars"], "value_vars")
                if value_error is not None:
                    return None, None, None, value_error
            return text, id_vars, value_vars, None

        if _SPLIT_SENTINEL not in text:
            return (
                None,
                None,
                None,
                (f"csv_melt requires text+id_vars arguments, or a single text split on {_SPLIT_SENTINEL!r}"),
            )
        if text.count(_SPLIT_SENTINEL) != 1:
            return None, None, None, "text contains more than one <<<CSV_MELT>>> sentinel"

        document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
        id_vars, id_error = cls._parse_columns(remainder.strip("\n"), "id_vars")
        if id_error is not None:
            return None, None, None, id_error
        return document, id_vars, None, None

    @staticmethod
    def _parse_columns(raw: object, label: str) -> tuple[list[str] | None, str | None]:
        """Parse and validate a comma-separated or sequence column list."""

        if isinstance(raw, (list, tuple)):
            names = [str(item).strip() for item in raw]
        else:
            text = str(raw).strip()
            if not text:
                return None, f"{label} list is empty"
            names = [part.strip() for part in text.split(",")]
        if not names or any(not name for name in names):
            return None, f"{label} column names must be non-empty"
        if len(set(names)) != len(names):
            return None, f"{label} columns must be unique"
        return names, None

    @staticmethod
    def _validate_columns(
        header: list[str],
        id_vars: list[str],
        value_vars: list[str] | None,
    ) -> str | None:
        """Validate selected columns against the CSV header."""

        requested = [*id_vars, *(value_vars or [])]
        missing = [name for name in requested if name not in header]
        if missing:
            return f"unknown column: {missing[0]!r}"
        if value_vars is not None and set(id_vars) & set(value_vars):
            return "id_vars and value_vars must be distinct"
        if _VARIABLE_COLUMN in id_vars or _VALUE_COLUMN in id_vars:
            return "variable and value output columns must not collide with id_vars"
        return None

    @staticmethod
    def _is_blank_row(row: list[str]) -> bool:
        """Return whether a parsed row has no non-whitespace cells."""

        return not row or all(not cell.strip() for cell in row)

    @staticmethod
    def _dump_csv(rows: list[list[str]]) -> str:
        """Serialize rows to canonical CSV with a trailing newline."""

        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerows(rows)
        return buffer.getvalue()

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
