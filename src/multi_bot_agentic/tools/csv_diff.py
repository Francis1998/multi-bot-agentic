"""Deterministic key-based CSV diff tool.

Agents often need to identify which records changed between two small CSV
exports without asking a model to compare every cell. This tool parses both
documents with stdlib :mod:`csv`, indexes rows by one or more primary-key
columns, and emits only added, removed, and changed key maps. It never executes
code or makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini
3.x / Kimi K2 workers.

Programmatic callers pass ``left``, ``right``, and ``key``. A single decision
payload may instead use ``<<<CSV_DIFF>>>`` between documents and
``<<<CSV_DIFF_KEY>>>`` before the key columns.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_TOTAL_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64
_SIDE_SENTINEL: Final[str] = "<<<CSV_DIFF>>>"
_KEY_SENTINEL: Final[str] = "<<<CSV_DIFF_KEY>>>"


@dataclass(frozen=True)
class _Table:
    """Parsed CSV rows indexed by primary key."""

    rows: dict[tuple[str, ...], dict[str, str]]
    row_count: int


class CsvDiffTool:
    """Compare two CSV documents by primary-key columns."""

    name = "csv_diff"
    description = (
        "Compares two CSV documents by key column(s) and returns JSON added/removed/changed key maps; "
        "max 20_000 chars combined, 500 rows, 64 columns."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Compare left and right CSV rows using caller-selected keys."""

        left, right, key_value, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert left is not None and right is not None and key_value is not None

        if not left.strip():
            return self._fail("left CSV is empty", {})
        if not right.strip():
            return self._fail("right CSV is empty", {})
        total_chars = len(left) + len(right)
        if total_chars > _MAX_TOTAL_CHARS:
            return self._fail(
                f"combined CSV text exceeds max_chars={_MAX_TOTAL_CHARS}",
                {"chars": total_chars},
            )

        keys, key_error = self._parse_keys(key_value)
        if key_error is not None:
            return self._fail(key_error, {})
        assert keys is not None

        left_table, left_error = self._parse_table(left, "left", keys)
        if left_error is not None:
            return self._fail(left_error, {"key": ",".join(keys)})
        right_table, right_error = self._parse_table(right, "right", keys)
        if right_error is not None:
            return self._fail(right_error, {"key": ",".join(keys)})
        assert left_table is not None and right_table is not None

        left_keys = set(left_table.rows)
        right_keys = set(right_table.rows)
        added = sorted(right_keys - left_keys)
        removed = sorted(left_keys - right_keys)
        changed = sorted(key for key in left_keys & right_keys if left_table.rows[key] != right_table.rows[key])
        result = {
            "added": [self._key_map(keys, key) for key in added],
            "removed": [self._key_map(keys, key) for key in removed],
            "changed": [self._key_map(keys, key) for key in changed],
        }
        content = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "key": ",".join(keys),
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
                "left_rows": left_table.row_count,
                "right_rows": right_table.row_count,
                "chars": len(content),
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, str | None, object | None, str | None]:
        """Resolve both documents and keys from arguments or sentinel forms."""

        key_value: object | None = arguments.get("key")
        if "right" in arguments:
            left = str(arguments.get("left", arguments.get("text", "")))
            right = str(arguments.get("right", ""))
            if key_value is None and _KEY_SENTINEL in right:
                if right.count(_KEY_SENTINEL) != 1:
                    return None, None, None, "right contains more than one <<<CSV_DIFF_KEY>>> sentinel"
                right, key_text = right.split(_KEY_SENTINEL, maxsplit=1)
                key_value = key_text
            if key_value is None:
                return None, None, None, "key column name(s) required"
            return left, right, key_value, None

        payload = str(arguments.get("left", arguments.get("text", "")))
        side_count = payload.count(_SIDE_SENTINEL)
        key_count = payload.count(_KEY_SENTINEL)
        if side_count == 1 and key_count == 1:
            left, remainder = payload.split(_SIDE_SENTINEL, maxsplit=1)
            right, sentinel_key = remainder.split(_KEY_SENTINEL, maxsplit=1)
            if key_value is not None:
                return None, None, None, "provide key argument or <<<CSV_DIFF_KEY>>>, not both"
            return left.strip("\n"), right.strip("\n"), sentinel_key, None
        if side_count == 1 and key_count == 0 and key_value is not None:
            left, right = payload.split(_SIDE_SENTINEL, maxsplit=1)
            return left.strip("\n"), right.strip("\n"), key_value, None
        if side_count == 2 and key_count == 0 and key_value is None:
            left, right, sentinel_key = payload.split(_SIDE_SENTINEL)
            return left.strip("\n"), right.strip("\n"), sentinel_key, None
        if side_count > 2 or key_count > 1:
            return None, None, None, "CSV diff payload contains too many sentinels"
        return (
            None,
            None,
            None,
            ("csv_diff requires left+right+key arguments, or text split with <<<CSV_DIFF>>> and <<<CSV_DIFF_KEY>>>"),
        )

    @staticmethod
    def _parse_keys(raw: object) -> tuple[list[str] | None, str | None]:
        """Parse one or more unique primary-key column names."""

        if isinstance(raw, (list, tuple)):
            keys = [str(item).strip() for item in raw]
        else:
            keys = [part.strip() for part in str(raw).strip().split(",")]
        if not keys or any(not key for key in keys):
            return None, "key column name(s) required"
        if len(set(keys)) != len(keys):
            return None, "key column names must be unique"
        return keys, None

    @classmethod
    def _parse_table(
        cls,
        document: str,
        side: str,
        keys: list[str],
    ) -> tuple[_Table | None, str | None]:
        """Parse and validate one CSV document, then index rows by key."""

        try:
            rows = list(csv.reader(io.StringIO(document), strict=True))
        except csv.Error as exc:
            return None, f"{side} CSV parse error: {exc}"

        while rows and cls._is_blank_row(rows[-1]):
            rows.pop()
        if not rows:
            return None, f"{side} CSV has no rows"
        if len(rows) > _MAX_ROWS + 1:
            return None, f"{side} CSV exceeds max_rows={_MAX_ROWS}"
        width = max(len(row) for row in rows)
        if width > _MAX_COLUMNS:
            return None, f"{side} CSV exceeds max_columns={_MAX_COLUMNS}"

        header = [cell.strip() for cell in rows[0]]
        if not header or any(not name for name in header):
            return None, f"{side} CSV header must contain non-empty named columns"
        if len(set(header)) != len(header):
            return None, f"{side} CSV header columns must be unique"
        missing = [key for key in keys if key not in header]
        if missing:
            return None, f"{side} CSV is missing key column: {missing[0]!r}"

        key_indices = [header.index(key) for key in keys]
        indexed: dict[tuple[str, ...], dict[str, str]] = {}
        row_count = 0
        for row_number, row in enumerate(rows[1:], start=2):
            if cls._is_blank_row(row):
                continue
            if len(row) != len(header):
                return (
                    None,
                    f"{side} CSV row {row_number} has {len(row)} columns; expected {len(header)}",
                )
            key = tuple(row[index] for index in key_indices)
            if any(not value.strip() for value in key):
                return None, f"{side} CSV row {row_number} has an empty key value"
            if key in indexed:
                return None, f"{side} CSV contains duplicate key: {key!r}"
            indexed[key] = dict(zip(header, row, strict=True))
            row_count += 1

        return _Table(rows=indexed, row_count=row_count), None

    @staticmethod
    def _is_blank_row(row: list[str]) -> bool:
        """Return whether a parsed row has no non-whitespace cells."""

        return not row or all(not cell.strip() for cell in row)

    @staticmethod
    def _key_map(columns: list[str], key: tuple[str, ...]) -> dict[str, str]:
        """Render a composite key as a column/value map."""

        return dict(zip(columns, key, strict=True))

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
