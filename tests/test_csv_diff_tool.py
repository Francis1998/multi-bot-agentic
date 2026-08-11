"""Tests for the key-based CSV diff tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_diff import CsvDiffTool

_LEFT = "id,name,status\n1,Ada,active\n2,Grace,active\n3,Kimi,active\n"
_RIGHT = "id,name,status\n2,Grace,inactive\n3,Kimi,active\n4,Gemini,active\n"


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_diff tool."""

    result = CsvDiffTool().execute(ToolInvocation(tool_name="csv_diff", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_csv_diff_reports_added_removed_and_changed_keys() -> None:
    """Only primary-key maps are emitted for each change category."""

    ok, content, metadata = _run(left=_LEFT, right=_RIGHT, key="id")

    assert ok is True
    assert json.loads(content) == {
        "added": [{"id": "4"}],
        "removed": [{"id": "1"}],
        "changed": [{"id": "2"}],
    }
    assert metadata["key"] == "id"
    assert metadata["added"] == 1
    assert metadata["removed"] == 1
    assert metadata["changed"] == 1
    assert metadata["left_rows"] == 3
    assert metadata["right_rows"] == 3
    assert "Grace" not in content


def test_csv_diff_supports_composite_keys_and_header_reordering() -> None:
    """Composite keys compare rows by column name rather than column order."""

    left = "region,id,model\nus,1,GPT-5.5\neu,1,Claude Sonnet 4.6\n"
    right = "model,id,region\nGPT-5.5,1,us\nKimi K2,1,eu\nGemini 3.x,2,apac\n"

    ok, content, metadata = _run(left=left, right=right, key=["region", "id"])

    assert ok is True
    assert json.loads(content) == {
        "added": [{"region": "apac", "id": "2"}],
        "removed": [],
        "changed": [{"region": "eu", "id": "1"}],
    }
    assert metadata["key"] == "region,id"


def test_csv_diff_accepts_sentinel_forms() -> None:
    """Distinct and repeated sentinels can carry both tables and the key."""

    distinct = f"{_LEFT}<<<CSV_DIFF>>>\n{_RIGHT}<<<CSV_DIFF_KEY>>>id"
    repeated = f"{_LEFT}<<<CSV_DIFF>>>{_RIGHT}<<<CSV_DIFF>>>id"
    ok_distinct, content_distinct, _m1 = _run(text=distinct)
    ok_repeated, content_repeated, _m2 = _run(text=repeated)

    assert ok_distinct is True
    assert ok_repeated is True
    assert json.loads(content_distinct) == json.loads(content_repeated)


def test_csv_diff_rejects_empty_oversized_and_missing_keys() -> None:
    """Required documents, size bounds, and key columns are enforced."""

    ok_empty, content_empty, _m1 = _run(left=_LEFT, right="", key="id")
    ok_big, content_big, metadata_big = _run(left="id\n" + ("x" * 20_000), right="id\n", key="id")
    ok_arg, content_arg, _m3 = _run(left=_LEFT, right=_RIGHT)
    ok_column, content_column, _m4 = _run(left=_LEFT, right=_RIGHT, key="missing")

    assert ok_empty is False and "right CSV is empty" in content_empty
    assert ok_big is False and "max_chars=20000" in content_big
    chars = metadata_big["chars"]
    assert isinstance(chars, int) and chars > 20_000
    assert ok_arg is False and "key column" in content_arg
    assert ok_column is False and "missing key column" in content_column


def test_csv_diff_rejects_malformed_and_non_primary_keys() -> None:
    """Malformed rows, empty key values, and duplicate keys are refused."""

    malformed = 'id,name\n1,"Ada\n'
    empty_key = "id,name\n,Ada\n"
    duplicate_key = "id,name\n1,Ada\n1,Grace\n"
    ok_bad, content_bad, _m1 = _run(left=malformed, right=_RIGHT, key="id")
    ok_empty_key, content_empty_key, _m2 = _run(left=empty_key, right=_RIGHT, key="id")
    ok_duplicate, content_duplicate, _m3 = _run(left=duplicate_key, right=_RIGHT, key="id")

    assert ok_bad is False and "parse error" in content_bad
    assert ok_empty_key is False and "empty key value" in content_empty_key
    assert ok_duplicate is False and "duplicate key" in content_duplicate


def test_csv_diff_rejects_row_and_column_bounds() -> None:
    """Both CSV inputs are capped at 500 data rows and 64 columns."""

    too_many_rows = "id\n" + "".join(f"{index}\n" for index in range(501))
    too_many_columns = ",".join(f"c{index}" for index in range(65)) + "\n"
    ok_rows, content_rows, _m1 = _run(left=too_many_rows, right="id\n", key="id")
    ok_columns, content_columns, _m2 = _run(left=too_many_columns, right="c0\n", key="c0")

    assert ok_rows is False and "max_rows=500" in content_rows
    assert ok_columns is False and "max_columns=64" in content_columns


def test_csv_diff_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_diff" in tools
    assert tools["csv_diff"].name == "csv_diff"
    SafetyPolicy().validate_tool("csv_diff")
    assert "csv_diff" in SafetyPolicy().allowed_tools
