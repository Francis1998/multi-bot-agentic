"""Tests for the semantic version compare tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.semver_compare import SemverCompareTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the semver_compare tool."""

    result = SemverCompareTool().execute(ToolInvocation(tool_name="semver_compare", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_semver_compare_orders_core_versions() -> None:
    """Core major.minor.patch ordering returns -1/0/1 with a human line."""

    ok_lt, content_lt, meta_lt = _run(version_a="1.0.0", version_b="1.0.1")
    ok_eq, content_eq, meta_eq = _run(version_a="2.3.4", version_b="2.3.4")
    ok_gt, content_gt, meta_gt = _run(version_a="3.0.0", version_b="2.9.9")

    assert ok_lt is True and content_lt.startswith("-1\n") and "1.0.0 < 1.0.1" in content_lt
    assert meta_lt["cmp"] == -1
    assert ok_eq is True and content_eq.startswith("0\n") and meta_eq["cmp"] == 0
    assert ok_gt is True and content_gt.startswith("1\n") and meta_gt["cmp"] == 1


def test_semver_compare_pre_release_and_sentinel() -> None:
    """Pre-release versions sort below release; sentinel form works."""

    ok, content, metadata = _run(version_a="1.0.0-alpha", version_b="1.0.0")
    assert ok is True
    assert content.startswith("-1\n")
    assert metadata["relation"] == "1.0.0-alpha < 1.0.0"

    ok2, content2, metadata2 = _run(version_a="1.0.0-alpha.1", version_b="1.0.0-alpha.beta")
    assert ok2 is True
    assert content2.startswith("-1\n")
    assert metadata2["cmp"] == -1

    ok3, content3, metadata3 = _run(text="1.2.3+build.1<<<SEMVER_COMPARE>>>1.2.3+other")
    assert ok3 is True
    assert content3.startswith("0\n")
    assert metadata3["cmp"] == 0


def test_semver_compare_rejects_invalid_and_missing_args() -> None:
    """Invalid SemVer strings and missing arguments fail."""

    ok_bad, content_bad, meta_bad = _run(version_a="1.0", version_b="1.0.0")
    ok_empty, content_empty, _m2 = _run(version_a="", version_b="1.0.0")
    ok_args, content_args, _m3 = _run(text="1.0.0")
    ok_dup, content_dup, _m4 = _run(text="1.0.0<<<SEMVER_COMPARE>>>2.0.0<<<SEMVER_COMPARE>>>3.0.0")

    assert ok_bad is False and "invalid semantic version" in content_bad
    assert meta_bad["version"] == "version_a"
    assert ok_empty is False and "empty" in content_empty
    assert ok_args is False and "version_a+version_b" in content_args
    assert ok_dup is False and "more than one" in content_dup


def test_semver_compare_mentions_model_versions_as_examples() -> None:
    """Agent-facing docs/examples can use product version labels as strings."""

    # Product labels are not SemVer; valid SemVer fixtures still cover GPT-5.5 /
    # Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workflow docs separately.
    ok, content, metadata = _run(version_a="5.5.0", version_b="4.6.0")
    assert ok is True
    assert content.startswith("1\n")
    assert metadata["cmp"] == 1


def test_semver_compare_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "semver_compare" in tools
    assert tools["semver_compare"].name == "semver_compare"
    SafetyPolicy().validate_tool("semver_compare")
    assert "semver_compare" in SafetyPolicy().allowed_tools
