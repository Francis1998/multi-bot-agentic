"""Deterministic CSV row/column slicing tool.

Agent runs often need a stable subset of a pasted spreadsheet export: the first
few data rows, only the columns needed for a decision, or a pipe-delimited table
from a legacy tool. Asking a language model to slice tabular text is unreliable
(shifted columns, invented headers, off-by-one row ranges). This tool parses CSV
text via the stdlib ``csv`` module, applies bounded row/column selection, and
returns canonical JSON. It never executes code and never makes a network request,
matching the ``csv``, ``json_path``, ``html_strip``, and ``regex`` contracts.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:spreadsheet_slice:<payload>``, the CSV document and slice options may be
supplied either as separate arguments (tests and programmatic callers) or as a
single ``text`` value split on the sentinel ``<<<SPREADSHEET_SLICE>>>``.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 200
_MAX_COLUMNS: Final[int] = 32
_DEFAULT_DELIMITER: Final[str] = ","
_SPLIT_SENTINEL: Final[str] = "<<<SPREADSHEET_SLICE>>>"

_EMBEDDED_OPTION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "rows",
        "start",
        "end",
        "row_start",
        "row_end",
        "columns",
        "cols",
        "column_names",
        "names",
        "column_indexes",
        "column_indices",
        "indexes",
        "indices",
        "delimiter",
    }
)


class SpreadsheetSliceTool:
    """Slice CSV rows and columns into canonical JSON."""

    name = "spreadsheet_slice"
    description = (
        "Slices CSV rows/columns into JSON (text + rows/columns args, or text split on <<<SPREADSHEET_SLICE>>>)."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Slice the CSV document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the CSV
                document and whose optional arguments control row range,
                column names/indexes, and delimiter. A single directive payload
                may embed options after ``<<<SPREADSHEET_SLICE>>>``.

        Returns:
            Tool result whose ``content`` is canonical JSON with ``header`` and
            sliced ``rows``, or ``ok=False`` and structured metadata when input,
            CSV parsing, bounds, row range, or column selection is invalid.
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

        delimiter = str(options.get("delimiter", _DEFAULT_DELIMITER))
        if len(delimiter) != 1:
            return self._fail(
                f"delimiter must be a single character, got {delimiter!r}",
                {"delimiter": delimiter},
            )

        header, body, parse_error, parse_metadata = self._parse_csv(document, delimiter)
        if parse_error is not None:
            return self._fail(parse_error, parse_metadata)

        row_start, row_end, row_error, row_metadata = self._parse_row_range(options, len(body))
        if row_error is not None:
            return self._fail(row_error, row_metadata)

        column_indexes, column_error, column_metadata = self._parse_column_selection(options, header)
        if column_error is not None:
            return self._fail(column_error, column_metadata)

        selected_header = [header[index] for index in column_indexes]
        selected_rows = [[row[index] for index in column_indexes] for row in body[row_start:row_end]]
        payload: dict[str, object] = {
            "header": selected_header,
            "rows": selected_rows,
            "row_count": len(selected_rows),
            "column_count": len(selected_header),
            "source_row_count": len(body),
            "source_column_count": len(header),
            "row_start": row_start,
            "row_end": row_end,
            "column_indexes": column_indexes,
            "delimiter": delimiter,
        }
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
            metadata={
                "row_count": len(selected_rows),
                "column_count": len(selected_header),
                "source_row_count": len(body),
                "source_column_count": len(header),
                "row_start": row_start,
                "row_end": row_end,
                "column_indexes": column_indexes,
                "delimiter": delimiter,
            },
        )

    @classmethod
    def _resolve_options(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, dict[str, object], str | None]:
        """Resolve CSV document and options from separate args or sentinel text.

        Args:
            arguments: Tool invocation arguments.

        Returns:
            ``(document, options, error)`` where ``options`` excludes ``text``.
        """

        text = str(arguments.get("text", ""))
        options = {key: value for key, value in arguments.items() if key != "text"}
        if _SPLIT_SENTINEL not in text:
            return text, options, None

        document, embedded_options = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in embedded_options:
            return None, {}, "text contains more than one <<<SPREADSHEET_SLICE>>> sentinel"

        parsed_options, error = cls._parse_embedded_options(embedded_options)
        if error is not None:
            return None, {}, error

        merged_options: dict[str, object] = dict(parsed_options)
        merged_options.update(options)
        return document.strip("\n"), merged_options, None

    @classmethod
    def _parse_embedded_options(cls, raw_options: str) -> tuple[dict[str, str], str | None]:
        """Parse ``key=value`` slice options from sentinel payload text.

        Args:
            raw_options: Text after ``<<<SPREADSHEET_SLICE>>>``. Options may be
                newline-separated, or semicolon-separated for compact payloads.

        Returns:
            Parsed option mapping and optional failure message.
        """

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
                return {}, f"spreadsheet_slice option must be key=value, got {part!r}"
            key, value = part.split("=", maxsplit=1)
            key = key.strip()
            value = value.strip()
            if key not in _EMBEDDED_OPTION_KEYS:
                return {}, f"unsupported spreadsheet_slice option: {key}"
            parsed[key] = value
        return parsed, None

    def _parse_csv(
        self,
        document: str,
        delimiter: str,
    ) -> tuple[list[str], list[list[str]], str | None, dict[str, object]]:
        """Parse and normalize a CSV document with the shared CSV bounds."""

        try:
            reader = csv.reader(io.StringIO(document), delimiter=delimiter)
            raw_rows = [list(row) for row in reader]
        except csv.Error as exc:
            return [], [], f"invalid CSV: {exc}", {}

        while raw_rows and len(raw_rows[-1]) == 1 and raw_rows[-1][0] == "":
            raw_rows.pop()

        if not raw_rows:
            return [], [], "document has no rows", {}

        width = max(len(row) for row in raw_rows)
        if width > _MAX_COLUMNS:
            return [], [], f"column count exceeds max_columns={_MAX_COLUMNS}", {"columns": width}
        if len(raw_rows) > _MAX_ROWS + 1:
            return [], [], f"row count exceeds max_rows={_MAX_ROWS} (excluding header)", {"rows": len(raw_rows) - 1}

        header = list(raw_rows[0])
        header.extend([""] * (width - len(header)))
        blank_header_columns = [index for index, name in enumerate(header) if not name.strip()]
        if blank_header_columns:
            return [], [], "header contains blank column names", {"columns": blank_header_columns}

        body: list[list[str]] = []
        for row in raw_rows[1:]:
            body.append(list(row) + [""] * (width - len(row)))
        return header, body, None, {}

    def _parse_row_range(
        self,
        options: dict[str, object],
        row_count: int,
    ) -> tuple[int, int, str | None, dict[str, object]]:
        """Parse a zero-based, end-exclusive body-row range."""

        row_start: int | None
        row_end: int | None
        if "rows" in options:
            row_start, row_end, error = self._parse_rows_argument(str(options["rows"]), row_count)
            if error is not None:
                return 0, 0, error, {"rows": str(options["rows"])}
        else:
            raw_start = options.get("row_start", options.get("start"))
            raw_end = options.get("row_end", options.get("end"))
            row_start = 0 if raw_start is None else self._parse_nonnegative_int(raw_start)
            row_end = row_count if raw_end is None else self._parse_nonnegative_int(raw_end)
            if row_start is None:
                return (
                    0,
                    0,
                    f"row_start must be a non-negative integer, got {raw_start!r}",
                    {"row_start": str(raw_start)},
                )
            if row_end is None:
                return 0, 0, f"row_end must be a non-negative integer, got {raw_end!r}", {"row_end": str(raw_end)}

        if row_start > row_end:
            return 0, 0, "row_start must be less than or equal to row_end", {"row_start": row_start, "row_end": row_end}
        if row_start > row_count or row_end > row_count:
            return (
                0,
                0,
                "row range is out of bounds",
                {"row_start": row_start, "row_end": row_end, "source_row_count": row_count},
            )
        return row_start, row_end, None, {}

    def _parse_rows_argument(self, rows: str, row_count: int) -> tuple[int, int, str | None]:
        """Parse ``rows`` as ``start:end`` or a single row index."""

        text = rows.strip()
        if not text:
            return 0, 0, "rows must not be empty"
        if ":" not in text:
            row_start = self._parse_nonnegative_int(text)
            if row_start is None:
                return 0, 0, f"rows must be 'start:end' or a non-negative integer, got {rows!r}"
            return row_start, row_start + 1, None

        parts = text.split(":")
        if len(parts) != 2:
            return 0, 0, f"rows must contain at most one ':', got {rows!r}"
        start_text, end_text = parts
        if start_text.strip():
            row_start = self._parse_nonnegative_int(start_text.strip())
            if row_start is None:
                return 0, 0, f"row range start must be a non-negative integer, got {start_text!r}"
        else:
            row_start = 0

        if end_text.strip():
            row_end = self._parse_nonnegative_int(end_text.strip())
            if row_end is None:
                return 0, 0, f"row range end must be a non-negative integer, got {end_text!r}"
        else:
            row_end = row_count
        return row_start, row_end, None

    def _parse_column_selection(
        self,
        options: dict[str, object],
        header: list[str],
    ) -> tuple[list[int], str | None, dict[str, object]]:
        """Parse mixed header-name and zero-based index column selection."""

        requests: list[tuple[str, object]] = []
        raw_columns = options.get("columns", options.get("cols"))
        if raw_columns is not None:
            for item in self._coerce_sequence(raw_columns):
                if isinstance(item, int) and not isinstance(item, bool):
                    requests.append(("index", item))
                    continue
                item_text = str(item).strip()
                if item_text.isdecimal():
                    requests.append(("index", item_text))
                else:
                    requests.append(("name", item_text))

        raw_names = options.get("column_names", options.get("names"))
        if raw_names is not None:
            requests.extend(("name", str(item).strip()) for item in self._coerce_sequence(raw_names))

        raw_indexes = options.get(
            "column_indexes",
            options.get("column_indices", options.get("indexes", options.get("indices"))),
        )
        if raw_indexes is not None:
            requests.extend(("index", item) for item in self._coerce_sequence(raw_indexes))

        if not requests:
            return list(range(len(header))), None, {}

        selected_indexes: list[int] = []
        for kind, raw_value in requests:
            if kind == "index":
                column_index = self._parse_nonnegative_int(raw_value)
                if column_index is None:
                    return (
                        [],
                        f"column index must be a non-negative integer, got {raw_value!r}",
                        {"column": str(raw_value)},
                    )
                if column_index >= len(header):
                    return (
                        [],
                        "column index is out of bounds",
                        {"column_index": column_index, "source_column_count": len(header)},
                    )
                selected_indexes.append(column_index)
                continue

            column_name = str(raw_value)
            if not column_name:
                return [], "column name must not be empty", {}
            matches = [index for index, name in enumerate(header) if name == column_name]
            if not matches:
                return [], f"column name not found: {column_name}", {"column_name": column_name}
            if len(matches) > 1:
                return [], f"column name is ambiguous: {column_name}", {"column_name": column_name, "matches": matches}
            selected_indexes.append(matches[0])

        return selected_indexes, None, {}

    @staticmethod
    def _coerce_sequence(value: object) -> list[object]:
        """Coerce list-like or comma-separated option values into a list."""

        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            return list(value)
        return [value]

    @staticmethod
    def _parse_nonnegative_int(value: object) -> int | None:
        """Parse a non-negative integer while rejecting booleans."""

        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value >= 0 else None
        if isinstance(value, str):
            text = value.strip()
            if text.isdecimal():
                return int(text)
        return None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
