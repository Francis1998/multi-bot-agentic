"""Tests for the TOML ↔ JSON bridge tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.toml_json import TomlJsonTool


def _run(document: str, direction: str = "to_json") -> tuple[bool, str]:
    """Execute the toml_json tool for a document.

    Args:
        document: Source document text.
        direction: Conversion direction (``to_json`` or ``to_toml``).

    Returns:
        Tuple of ``(ok, content)`` from the tool result.
    """

    result = TomlJsonTool().execute(
        ToolInvocation(tool_name="toml_json", arguments={"text": document, "direction": direction})
    )
    return result.ok, result.content


def test_toml_json_converts_toml_to_json() -> None:
    """TOML input is parsed and emitted as sorted JSON."""

    ok, content = _run(
        """
b = 1
[models]
names = ["Kimi K2", "Claude Sonnet 4.6"]
[a]
z = true
retries = 2
""",
        direction="to_json",
    )

    assert ok is True
    assert content == (
        "{\n"
        '  "a": {\n'
        '    "retries": 2,\n'
        '    "z": true\n'
        "  },\n"
        '  "b": 1,\n'
        '  "models": {\n'
        '    "names": [\n'
        '      "Kimi K2",\n'
        '      "Claude Sonnet 4.6"\n'
        "    ]\n"
        "  }\n"
        "}"
    )


def test_toml_json_converts_json_to_toml() -> None:
    """JSON input is parsed and emitted as canonical TOML."""

    ok, content = _run(
        '{"b": 1, "a": {"z": true, "retries": 2}, "models": {"names": ["Gemini 3.x", "GPT-5.5"]}}',
        direction="to_toml",
    )

    assert ok is True
    assert content == "\n".join(
        [
            "b = 1",
            "",
            "[a]",
            "retries = 2",
            "z = true",
            "",
            "[models]",
            'names = ["Gemini 3.x", "GPT-5.5"]',
        ]
    )


def test_toml_json_defaults_to_json_direction() -> None:
    """Omitting direction converts TOML to JSON."""

    result = TomlJsonTool().execute(ToolInvocation(tool_name="toml_json", arguments={"text": "enabled = true\n"}))

    assert result.ok is True
    assert result.content == '{\n  "enabled": true\n}'
    assert result.metadata["direction"] == "to_json"


def test_toml_json_rejects_invalid_toml() -> None:
    """Malformed TOML returns a structured failure."""

    ok, content = _run('models = ["GPT-5.5", Kimi K2', direction="to_json")

    assert ok is False
    assert "invalid TOML" in content


def test_toml_json_rejects_invalid_json() -> None:
    """Malformed JSON returns a structured failure."""

    ok, content = _run('{"models": [GPT-5.5]}', direction="to_toml")

    assert ok is False
    assert "invalid JSON" in content


def test_toml_json_rejects_empty_document() -> None:
    """An empty document is reported as a failure."""

    ok, content = _run("   ")

    assert ok is False
    assert "empty" in content


def test_toml_json_rejects_oversized_document() -> None:
    """Documents above the fixed character cap are refused before parsing."""

    ok, content = _run("text = " + ('"' + ("x" * 20_001) + '"'))

    assert ok is False
    assert "max_chars=20000" in content


def test_toml_json_rejects_datetime_values() -> None:
    """Offset date-time values are outside the portable scalar subset."""

    ok, content = _run("released = 2026-07-28T12:00:00Z", direction="to_json")

    assert ok is False
    assert "invalid TOML" in content
    assert "unsupported" in content


def test_toml_json_rejects_null_in_json() -> None:
    """JSON null cannot be represented in TOML."""

    ok, content = _run('{"enabled": null}', direction="to_toml")

    assert ok is False
    assert "invalid JSON" in content
    assert "null" in content


def test_toml_json_rejects_non_finite_json() -> None:
    """Non-finite JSON numbers are refused."""

    ok, content = _run('{"value": NaN}', direction="to_toml")

    assert ok is False
    assert "invalid JSON" in content


def test_toml_json_rejects_invalid_direction() -> None:
    """Unknown direction values return a structured failure."""

    ok, content = _run("enabled = true\n", direction="to_yaml")

    assert ok is False
    assert "invalid direction" in content


def test_toml_json_reports_metadata() -> None:
    """Successful results include direction and top-level metadata."""

    result = TomlJsonTool().execute(
        ToolInvocation(
            tool_name="toml_json",
            arguments={
                "text": '{"enabled": true, "models": ["GPT-5.5", "Gemini 3.x"]}',
                "direction": "to_toml",
            },
        )
    )

    assert result.ok is True
    assert "enabled = true" in result.content
    assert result.metadata == {"direction": "to_toml", "top_level_type": "dict", "keys": 2}


def test_toml_json_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is available through the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "toml_json" in tools
    assert tools["toml_json"].name == "toml_json"
    SafetyPolicy().validate_tool("toml_json")
    assert "toml_json" in SafetyPolicy().allowed_tools
