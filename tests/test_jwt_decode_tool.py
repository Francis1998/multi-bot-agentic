"""Tests for the JWT header+payload decode tool."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.jwt_decode import JwtDecodeTool


def _b64url(data: dict[str, object]) -> str:
    """Encode a JSON object as an unpadded base64url JWT segment."""

    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _token(header: dict[str, object], payload: dict[str, object], signature: str = "sig") -> str:
    """Build a three-segment JWT-like token from header and payload objects."""

    return f"{_b64url(header)}.{_b64url(payload)}.{signature}"


def _run(text: str) -> tuple[bool, str, dict[str, object]]:
    """Execute the jwt_decode tool.

    Args:
        text: JWT token string.

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = JwtDecodeTool().execute(ToolInvocation(tool_name="jwt_decode", arguments={"text": text}))
    return result.ok, result.content, result.metadata


def test_jwt_decode_returns_header_and_payload_json() -> None:
    """Happy path decodes header and payload without verifying the signature."""

    token = _token({"alg": "none", "typ": "JWT"}, {"sub": "alice", "role": "viewer"})
    ok, content, metadata = _run(token)

    assert ok is True
    parsed = json.loads(content)
    assert parsed == {
        "header": {"alg": "none", "typ": "JWT"},
        "payload": {"role": "viewer", "sub": "alice"},
    }
    assert metadata["verified"] is False
    assert metadata["trusted"] is False


def test_jwt_decode_ignores_signature_and_never_verifies() -> None:
    """Any signature segment is ignored; metadata always reports unverified."""

    token = _token({"alg": "HS256"}, {"iss": "example"}, signature="definitely-not-valid")
    ok, content, metadata = _run(token)

    assert ok is True
    assert json.loads(content)["payload"]["iss"] == "example"
    assert metadata["verified"] is False
    assert metadata["trusted"] is False


def test_jwt_decode_rejects_empty_and_oversized_tokens() -> None:
    """Empty and oversized tokens are refused."""

    ok_empty, content_empty, _m1 = _run("   ")
    ok_big, content_big, metadata_big = _run("a." + ("b" * 20_001) + ".c")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    value = metadata_big["chars"]
    assert isinstance(value, int)
    assert value > 20_000


def test_jwt_decode_rejects_wrong_segment_count() -> None:
    """Tokens without exactly three segments fail structurally."""

    ok, content, metadata = _run("only.two")

    assert ok is False
    assert "exactly 3" in content
    assert metadata["segments"] == 2


def test_jwt_decode_rejects_invalid_base64url_and_json() -> None:
    """Malformed segments return structured failures."""

    ok_b64, content_b64, metadata_b64 = _run("@@@.payload.sig")
    bad_payload = f"{_b64url({'alg': 'none'})}.{base64.urlsafe_b64encode(b'not-json').decode().rstrip('=')}.x"
    ok_json, content_json, metadata_json = _run(bad_payload)

    assert ok_b64 is False
    assert "base64url" in content_b64
    assert metadata_b64["segment"] == "header"
    assert ok_json is False
    assert "JSON" in content_json
    assert metadata_json["segment"] == "payload"


def test_jwt_decode_rejects_non_object_segments() -> None:
    """Header and payload must be JSON objects."""

    array_segment = base64.urlsafe_b64encode(b"[1]").decode("ascii").rstrip("=")
    token = f"{array_segment}.{_b64url({'sub': 'x'})}.sig"
    ok, content, metadata = _run(token)

    assert ok is False
    assert "JSON object" in content
    assert metadata["segment"] == "header"


def test_jwt_decode_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "jwt_decode" in tools
    assert tools["jwt_decode"].name == "jwt_decode"
    SafetyPolicy().validate_tool("jwt_decode")
    assert "jwt_decode" in SafetyPolicy().allowed_tools
