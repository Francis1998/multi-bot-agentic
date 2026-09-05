"""Tests for the geohash tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.geohash import GeohashTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the geohash tool."""

    result = GeohashTool().execute(ToolInvocation(tool_name="geohash", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_geohash_encode_known_point() -> None:
    """encode mode returns a known geohash for a classic test point."""

    ok, content, metadata = _run(lat=37.7749, lon=-122.4194, precision=7)
    assert ok is True
    assert content == "9q8yyk8"
    assert metadata["mode"] == "encode"
    assert metadata["precision"] == 7


def test_geohash_decode_roundtrips_center() -> None:
    """decode mode returns lat,lon center near the encoded cell."""

    ok, content, metadata = _run(geohash="9q8yyk8", mode="decode")
    assert ok is True
    assert "," in content
    lat = float(metadata["lat"])  # type: ignore[arg-type]
    lon = float(metadata["lon"])  # type: ignore[arg-type]
    assert abs(lat - 37.7749) < 0.01
    assert abs(lon - (-122.4194)) < 0.01
    assert metadata["mode"] == "decode"


def test_geohash_default_mode_is_encode() -> None:
    """Omitting mode defaults to encode."""

    ok, content, metadata = _run(latitude=0.0, longitude=0.0, precision=1)
    assert ok is True and content == "s"
    assert metadata["mode"] == "encode"


def test_geohash_rejects_bad_precision_and_coords() -> None:
    """Precision bounds and coordinate ranges are enforced."""

    ok_p, content_p, metadata_p = _run(lat=0, lon=0, precision=13)
    assert ok_p is False and "precision" in content_p
    assert metadata_p["precision"] == 13
    ok_lat, content_lat, _ = _run(lat=91, lon=0)
    assert ok_lat is False and "lat out of range" in content_lat
    ok_lon, content_lon, _ = _run(lat=0, lon=181)
    assert ok_lon is False and "lon out of range" in content_lon


def test_geohash_rejects_empty_bad_mode_missing() -> None:
    """Structural failures for bad inputs and modes."""

    assert _run(mode="encode")[0] is False
    assert _run(mode="decode")[0] is False
    assert _run(geohash="", mode="decode")[0] is False
    ok_mode, content_mode, metadata_mode = _run(mode="hash", lat=0, lon=0)
    assert ok_mode is False and "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "hash"
    ok_bad, content_bad, _ = _run(geohash="!!!!", mode="decode")
    assert ok_bad is False and "invalid" in content_bad


def test_geohash_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "geohash" in tools
    assert tools["geohash"].name == "geohash"
    SafetyPolicy().validate_tool("geohash")
    assert "geohash" in SafetyPolicy().allowed_tools
