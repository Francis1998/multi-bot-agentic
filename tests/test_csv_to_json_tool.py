"""Tests for the csv_to_json tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_to_json import CsvToJsonTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_to_json tool."""

    result = CsvToJsonTool().execute(ToolInvocation(tool_name="csv_to_json", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_csv_to_json_parses_header_objects() -> None:
    """Header row keys objects in the JSON array."""

    csv_text = "name,role\nAda,engineer\nGrace,researcher\n"
    ok, content, metadata = _run(csv=csv_text)

    assert ok is True
    assert json.loads(content) == [
        {"name": "Ada", "role": "engineer"},
        {"name": "Grace", "role": "researcher"},
    ]
    assert metadata["rows"] == 2
    assert metadata["columns"] == 2
    assert metadata["header"] == ["name", "role"]


def test_csv_to_json_respects_delimiter_and_pads_short_rows() -> None:
    """Optional delimiter works; short rows pad with empty strings."""

    csv_text = "a|b|c\n1|2\n"
    ok, content, metadata = _run(csv=csv_text, delimiter="|")

    assert ok is True
    assert json.loads(content) == [{"a": "1", "b": "2", "c": ""}]
    assert metadata["delimiter"] == "|"


def test_csv_to_json_accepts_text_alias() -> None:
    """``text`` is accepted as an alias for ``csv``."""

    ok, content, _metadata = _run(text="id,label\n1,alpha\n")
    assert ok is True
    assert json.loads(content) == [{"id": "1", "label": "alpha"}]


def test_csv_to_json_rejects_missing_blank_header_and_bounds() -> None:
    """Missing/empty/blank-header/oversized/bad-delimiter inputs fail."""

    ok_missing, content_missing, _m0 = _run()
    ok_empty, content_empty, _m1 = _run(csv="   ")
    ok_header, content_header, _m2 = _run(csv="\n1,2\n")
    ok_blank, content_blank, _m3 = _run(csv="name,\nAda,1\n")
    ok_delim, content_delim, metadata_delim = _run(csv="a,b\n1,2\n", delimiter="||")
    ok_big, content_big, metadata_big = _run(csv="a\n" + ("x\n" * 20_000))

    assert ok_missing is False and "missing required argument" in content_missing
    assert ok_empty is False and "empty" in content_empty
    assert ok_header is False and "header row is required" in content_header
    assert ok_blank is False and "header row is required" in content_blank
    assert ok_delim is False and "delimiter must be a single character" in content_delim
    assert metadata_delim["delimiter"] == "||"
    assert ok_big is False and "max_chars" in content_big
    chars = metadata_big["chars"]
    assert isinstance(chars, int) and chars > 20_000


def test_csv_to_json_rejects_too_many_rows() -> None:
    """More than 500 body rows fails."""

    header = "col\n"
    body = "".join(f"{i}\n" for i in range(501))
    ok, content, metadata = _run(csv=header + body)
    assert ok is False
    assert "max_rows" in content
    assert metadata["rows"] == 501


def test_csv_to_json_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_to_json" in tools
    assert tools["csv_to_json"].name == "csv_to_json"
    SafetyPolicy().validate_tool("csv_to_json")
    assert "csv_to_json" in SafetyPolicy().allowed_tools
