"""Deterministic bounded CSV sliding-window tool.

Agents often need consecutive row windows from a table without asking a model
to copy headers or slice rows by hand. This tool validates a CSV document,
preserves the header once per window, and emits sliding windows over data rows.
It never executes code or makes network requests. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Arguments: ``text`` (CSV), ``window_size``, optional ``step`` (default 1),
``start_row`` (0-based data-row offset, default 0), and optional ``index`` to
return a single window.
"""

from __future__ import annotations

import csv
import io
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64
_DEFAULT_STEP: Final[int] = 1
_DEFAULT_START_ROW: Final[int] = 0


class CsvWindowTool:
    """Emit sliding windows of CSV data rows with a shared header."""

    name = "csv_window"
    description = (
        "Emits sliding CSV row windows with the header preserved once per "
        "window (window_size required; step default 1; start_row default 0; "
        "optional index); max 20_000 chars, 500 rows, and 64 columns."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Validate CSV input and emit one or more window blocks."""

        text = str(invocation.arguments.get("text", ""))
        if not text.strip():
            return self._fail("CSV input is empty", {})
        if len(text) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"CSV input exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(text)},
            )

        window_size, step, start_row, index, resolve_error = self._resolve_options(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert window_size is not None and step is not None and start_row is not None

        try:
            rows = list(csv.reader(io.StringIO(text), strict=True))
        except csv.Error as exc:
            return self._fail(f"csv parse error: {exc}", {})

        if not rows:
            return self._fail("csv document is empty", {})

        header = [cell.strip() for cell in rows[0]]
        if not header or any(not name for name in header):
            return self._fail("csv header must contain non-empty named columns", {})
        if len(set(header)) != len(header):
            return self._fail("csv header columns must be unique", {})
        if len(header) > _MAX_COLUMNS:
            return self._fail(
                f"csv exceeds max_columns={_MAX_COLUMNS}",
                {"columns": len(header)},
            )

        data_rows: list[list[str]] = []
        for row_index, row in enumerate(rows[1:], start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            if len(row) != len(header):
                return self._fail(
                    f"csv row {row_index} has {len(row)} columns; expected {len(header)}",
                    {"columns": len(row), "expected_columns": len(header), "row": row_index},
                )
            data_rows.append(row)
            if len(data_rows) > _MAX_ROWS:
                return self._fail(
                    f"csv exceeds max_rows={_MAX_ROWS}",
                    {"rows": len(data_rows)},
                )

        if start_row > len(data_rows):
            return self._fail(
                f"start_row {start_row} is past the end of {len(data_rows)} data rows",
                {"start_row": start_row, "rows": len(data_rows)},
            )

        sliced = data_rows[start_row:]
        windows = self._build_windows(sliced, window_size, step)
        if not windows:
            return self._fail(
                "no complete windows fit the requested window_size",
                {
                    "rows": len(sliced),
                    "start_row": start_row,
                    "step": step,
                    "window_size": window_size,
                },
            )

        if index is not None:
            if index < 0 or index >= len(windows):
                return self._fail(
                    f"index {index} is out of range for {len(windows)} windows",
                    {"index": index, "windows": len(windows)},
                )
            selected = [windows[index]]
        else:
            selected = windows

        blocks = [self._format_window(header, window) for window in selected]
        content = "\n".join(blocks)
        if len(content) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"windowed csv exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(content), "input_chars": len(text)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "chars": len(content),
                "columns": len(header),
                "index": index,
                "input_chars": len(text),
                "rows": len(data_rows),
                "start_row": start_row,
                "step": step,
                "window_rows": window_size,
                "windows": len(selected),
                "windows_available": len(windows),
            },
        )

    @classmethod
    def _resolve_options(
        cls,
        arguments: dict[str, object],
    ) -> tuple[int | None, int | None, int | None, int | None, str | None]:
        """Parse and validate window_size, step, start_row, and optional index."""

        if "window_size" not in arguments:
            return None, None, None, None, "window_size is required"

        window_size = cls._parse_positive_int(arguments["window_size"], "window_size")
        if isinstance(window_size, str):
            return None, None, None, None, window_size

        step_raw = arguments.get("step", _DEFAULT_STEP)
        step = cls._parse_positive_int(step_raw, "step")
        if isinstance(step, str):
            return None, None, None, None, step

        start_raw = arguments.get("start_row", _DEFAULT_START_ROW)
        start_row = cls._parse_non_negative_int(start_raw, "start_row")
        if isinstance(start_row, str):
            return None, None, None, None, start_row

        index: int | None = None
        if "index" in arguments:
            parsed_index = cls._parse_non_negative_int(arguments["index"], "index")
            if isinstance(parsed_index, str):
                return None, None, None, None, parsed_index
            index = parsed_index

        return window_size, step, start_row, index, None

    @staticmethod
    def _parse_positive_int(value: object, name: str) -> int | str:
        """Parse a strictly positive integer option."""

        if isinstance(value, bool) or not isinstance(value, int):
            if isinstance(value, str) and value.strip().isdigit():
                parsed = int(value.strip())
            else:
                return f"{name} must be a positive integer, got {value!r}"
        else:
            parsed = value
        if parsed < 1:
            return f"{name} must be a positive integer, got {value!r}"
        return parsed

    @staticmethod
    def _parse_non_negative_int(value: object, name: str) -> int | str:
        """Parse a non-negative integer option."""

        if isinstance(value, bool) or not isinstance(value, int):
            if isinstance(value, str) and value.strip().isdigit():
                parsed = int(value.strip())
            else:
                return f"{name} must be a non-negative integer, got {value!r}"
        else:
            parsed = value
        if parsed < 0:
            return f"{name} must be a non-negative integer, got {value!r}"
        return parsed

    @staticmethod
    def _build_windows(rows: list[list[str]], window_size: int, step: int) -> list[list[list[str]]]:
        """Build consecutive sliding windows of exact window_size."""

        windows: list[list[list[str]]] = []
        if window_size > len(rows):
            return windows
        for start in range(0, len(rows) - window_size + 1, step):
            windows.append(rows[start : start + window_size])
        return windows

    @staticmethod
    def _format_window(header: list[str], window: list[list[str]]) -> str:
        """Serialize one header-preserving window block."""

        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(window)
        return out.getvalue()

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
