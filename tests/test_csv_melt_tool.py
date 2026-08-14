"""Tests for the CSV melt tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_melt import CsvMeltTool

_SAMPLE = "model,region,latency,cost\nGPT-5.5,us,120,4\nClaude Sonnet 4.6,eu,150,3\n"


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_melt tool."""

    result = CsvMeltTool().execute(ToolInvocation(tool_name="csv_melt", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_csv_melt_unpivots_all_non_id_columns_by_default() -> None:
    """Every non-identifier column becomes a variable/value row."""

    ok, content, metadata = _run(text=_SAMPLE, id_vars=["model", "region"])

    assert ok is True
    assert content == (
        "model,region,variable,value\n"
        "GPT-5.5,us,latency,120\n"
        "GPT-5.5,us,cost,4\n"
        "Claude Sonnet 4.6,eu,latency,150\n"
        "Claude Sonnet 4.6,eu,cost,3\n"
    )
    assert metadata["rows"] == 4
    assert metadata["columns"] == 4
    assert metadata["id_vars"] == "model,region"
    assert metadata["value_vars"] == "latency,cost"


def test_csv_melt_supports_explicit_value_vars() -> None:
    """value_vars limits and orders the columns that are melted."""

    ok, content, metadata = _run(text=_SAMPLE, id_vars="model", value_vars="cost,latency")

    assert ok is True
    assert content == (
        "model,variable,value\n"
        "GPT-5.5,cost,4\n"
        "GPT-5.5,latency,120\n"
        "Claude Sonnet 4.6,cost,3\n"
        "Claude Sonnet 4.6,latency,150\n"
    )
    assert metadata["value_vars"] == "cost,latency"


def test_csv_melt_accepts_sentinel_form() -> None:
    """The sentinel suffix supplies id_vars and melts all other columns."""

    document = "model,score,rank\nGemini 3.x,8,2\nKimi K2,9,1\n"
    ok, content, metadata = _run(text=f"{document}<<<CSV_MELT>>>model")

    assert ok is True
    assert content == ("model,variable,value\nGemini 3.x,score,8\nGemini 3.x,rank,2\nKimi K2,score,9\nKimi K2,rank,1\n")
    assert metadata["rows"] == 4


def test_csv_melt_rejects_empty_oversized_and_invalid_columns() -> None:
    """Empty, oversized, and invalid column selections fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="", id_vars="model")
    ok_big, content_big, metadata_big = _run(text="model\n" + ("x" * 20_000), id_vars="model")
    ok_args, content_args, _m3 = _run(text=_SAMPLE)
    ok_missing, content_missing, _m4 = _run(text=_SAMPLE, id_vars="missing")
    ok_overlap, content_overlap, _m5 = _run(text=_SAMPLE, id_vars="model", value_vars="model,cost")
    ok_collision, content_collision, _m6 = _run(text="variable,x\na,1\n", id_vars="variable")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars=20000" in content_big
    chars = metadata_big["chars"]
    assert isinstance(chars, int) and chars > 20_000
    assert ok_args is False and "text+id_vars" in content_args
    assert ok_missing is False and "unknown column" in content_missing
    assert ok_overlap is False and "distinct" in content_overlap
    assert ok_collision is False and "collide" in content_collision


def test_csv_melt_rejects_table_and_output_bounds() -> None:
    """Input and expanded output remain within row and column caps."""

    too_many_rows = "id,x\n" + "".join(f"{index},1\n" for index in range(501))
    too_many_columns = ",".join(["id", *[f"c{index}" for index in range(64)]]) + "\n"
    max_input_columns = [f"c{index}" for index in range(64)]
    too_many_output_columns = ",".join(max_input_columns) + "\n"
    expansion = "id,x,y\n" + "".join(f"{index},1,2\n" for index in range(251))

    ok_rows, content_rows, _m1 = _run(text=too_many_rows, id_vars="id")
    ok_columns, content_columns, _m2 = _run(text=too_many_columns, id_vars="id")
    ok_output_columns, content_output_columns, metadata_output_columns = _run(
        text=too_many_output_columns,
        id_vars=max_input_columns[:-1],
    )
    ok_output, content_output, metadata_output = _run(text=expansion, id_vars="id")

    assert ok_rows is False and "max_rows=500" in content_rows
    assert ok_columns is False and "max_columns=64" in content_columns
    assert ok_output_columns is False and "melt output exceeds max_columns=64" in content_output_columns
    assert metadata_output_columns["columns"] == 65
    assert ok_output is False and "melt output exceeds max_rows=500" in content_output
    assert metadata_output["rows"] == 501


def test_csv_melt_rejects_duplicate_headers_and_uneven_rows() -> None:
    """Ambiguous headers and rows with the wrong width are refused."""

    ok_header, content_header, _m1 = _run(text="id,x,x\na,1,2\n", id_vars="id")
    ok_row, content_row, _m2 = _run(text="id,x,y\na,1\n", id_vars="id")

    assert ok_header is False and "unique" in content_header
    assert ok_row is False and "expected 3" in content_row


def test_csv_melt_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_melt" in tools
    assert tools["csv_melt"].name == "csv_melt"
    SafetyPolicy().validate_tool("csv_melt")
    assert "csv_melt" in SafetyPolicy().allowed_tools
