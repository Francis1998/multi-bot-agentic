"""CSV join / lookup tool for agent tabular handoffs.

Agents often need to join two small CSV tables on a key column before the next
LLM turn. Asking a language model to invent join results drops rows and
duplicates keys. This tool uses stdlib :mod:`csv` to perform an inner or left
join and emit the combined table. It never executes code and never makes
network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
"""

from __future__ import annotations

import csv
import io
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_TOTAL_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64
_ALLOWED_HOW: Final[frozenset[str]] = frozenset({"inner", "left"})
_DEFAULT_HOW: Final[str] = "inner"


class CsvJoinTool:
    """Join two CSV tables on a key column (inner or left)."""

    name = "csv_join"
    description = (
        "Joins two CSV tables on a key column (how inner|left; on or "
        "left_on+right_on); max 20_000 chars total, 500 rows."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Join left and right CSV documents.

        Args:
            invocation: Tool invocation whose ``left`` (or ``text``) and
                ``right`` arguments hold CSV tables, ``on`` is a shared key
                column (or ``left_on`` / ``right_on`` for differing names), and
                ``how`` is ``inner`` (default) or ``left``.

        Returns:
            Tool result with joined CSV text, or ``ok=False`` when input is
            empty, oversized, malformed, or arguments are invalid.
        """

        left_doc, right_doc, resolve_error = self._resolve_sides(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert left_doc is not None and right_doc is not None

        total_chars = len(left_doc) + len(right_doc)
        if total_chars > _MAX_TOTAL_CHARS:
            return self._fail(
                f"combined text exceeds max_chars={_MAX_TOTAL_CHARS}",
                {"chars": total_chars},
            )

        how = str(invocation.arguments.get("how", _DEFAULT_HOW)).strip().lower()
        if how not in _ALLOWED_HOW:
            return self._fail(
                f"unsupported how: {how!r}; must be inner or left",
                {"how": how},
            )

        left_on, right_on, key_error = self._resolve_keys(invocation.arguments)
        if key_error is not None:
            return self._fail(key_error, {"how": how})
        assert left_on is not None and right_on is not None

        left_rows, left_err = self._parse_csv(left_doc, "left")
        if left_err is not None:
            return self._fail(left_err, {"how": how})
        right_rows, right_err = self._parse_csv(right_doc, "right")
        if right_err is not None:
            return self._fail(right_err, {"how": how})
        assert left_rows is not None and right_rows is not None

        left_header = [cell.strip() for cell in left_rows[0]]
        right_header = [cell.strip() for cell in right_rows[0]]
        if left_on not in left_header:
            return self._fail(
                f"unknown left column: {left_on!r}",
                {"columns": ",".join(left_header)},
            )
        if right_on not in right_header:
            return self._fail(
                f"unknown right column: {right_on!r}",
                {"columns": ",".join(right_header)},
            )

        left_key_i = left_header.index(left_on)
        right_key_i = right_header.index(right_on)

        # Right non-key columns; rename collisions with left_ prefix avoidance.
        right_extra = [name for i, name in enumerate(right_header) if i != right_key_i]
        renamed_right: list[str] = []
        left_names = set(left_header)
        for name in right_extra:
            out_name = name
            if out_name in left_names or out_name == left_on:
                out_name = f"right_{name}"
            renamed_right.append(out_name)

        right_index: dict[str, list[list[str]]] = {}
        for row in right_rows[1:]:
            if not row or all(not cell.strip() for cell in row):
                continue
            padded = row + [""] * (len(right_header) - len(row))
            key = padded[right_key_i]
            extras = [padded[i] for i, name in enumerate(right_header) if i != right_key_i]
            right_index.setdefault(key, []).append(extras)

        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        # Prefer a single key column name when keys match; else keep left key name.
        out_header = [*left_header, *renamed_right]
        writer.writerow(out_header)

        out_rows = 0
        for row in left_rows[1:]:
            if not row or all(not cell.strip() for cell in row):
                continue
            padded = row + [""] * (len(left_header) - len(row))
            key = padded[left_key_i]
            matches = right_index.get(key, [])
            if matches:
                for extras in matches:
                    writer.writerow([*padded[: len(left_header)], *extras])
                    out_rows += 1
            elif how == "left":
                writer.writerow([*padded[: len(left_header)], *[""] * len(renamed_right)])
                out_rows += 1

        content = out.getvalue()
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "how": how,
                "left_on": left_on,
                "right_on": right_on,
                "rows": out_rows,
                "columns": len(out_header),
                "chars": len(content),
            },
        )

    @classmethod
    def _resolve_sides(cls, arguments: dict[str, object]) -> tuple[str | None, str | None, str | None]:
        """Resolve left/right CSV documents from ``left``/``right`` or ``text``/``right``."""

        right = str(arguments.get("right", "")).strip()
        if not right:
            return None, None, "right CSV is empty"

        if "left" in arguments:
            left = str(arguments.get("left", "")).strip()
        elif "text" in arguments:
            left = str(arguments.get("text", "")).strip()
        else:
            left = ""

        if not left:
            return None, None, "left CSV is empty (provide left or text)"
        return left, right, None

    @classmethod
    def _resolve_keys(cls, arguments: dict[str, object]) -> tuple[str | None, str | None, str | None]:
        """Resolve join key column names from ``on`` or ``left_on``/``right_on``."""

        on_raw = str(arguments.get("on", "")).strip()
        left_on = str(arguments.get("left_on", "")).strip()
        right_on = str(arguments.get("right_on", "")).strip()

        if on_raw:
            if left_on or right_on:
                return None, None, "provide either on, or left_on+right_on, not both"
            return on_raw, on_raw, None
        if left_on and right_on:
            return left_on, right_on, None
        if left_on or right_on:
            return None, None, "left_on and right_on are both required when on is omitted"
        return None, None, "on (or left_on+right_on) key column required"

    @classmethod
    def _parse_csv(cls, document: str, side: str) -> tuple[list[list[str]] | None, str | None]:
        """Parse a CSV document with row/column bounds."""

        try:
            rows = list(csv.reader(io.StringIO(document)))
        except csv.Error as exc:
            return None, f"{side} csv parse error: {exc}"

        if not rows or not any(cell.strip() for row in rows for cell in row):
            return None, f"{side} csv has no data rows"
        if len(rows) > _MAX_ROWS + 1:
            return None, f"{side} csv exceeds max_rows={_MAX_ROWS}"
        if any(len(row) > _MAX_COLUMNS for row in rows):
            return None, f"{side} csv exceeds max_columns={_MAX_COLUMNS}"

        header = [cell.strip() for cell in rows[0]]
        if not header or any(not name for name in header):
            return None, f"{side} csv header must be non-empty named columns"
        if len(set(header)) != len(header):
            return None, f"{side} csv header columns must be unique"
        return rows, None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
