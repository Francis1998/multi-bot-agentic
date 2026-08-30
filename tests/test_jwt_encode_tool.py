"""Tests for the JWT HS256 encode tool."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.jwt_decode import JwtDecodeTool
from multi_bot_agentic.tools.jwt_encode import JwtEncodeTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the jwt_encode tool."""

    result = JwtEncodeTool().execute(ToolInvocation(tool_name="jwt_encode", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def _b64url_bytes(data: bytes) -> str:
    """Encode bytes as unpadded base64url."""

    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def test_jwt_encode_builds_verifiable_hs256_token() -> None:
    """Happy path returns a three-segment HS256 JWT."""

    payload = {"sub": "alice", "role": "viewer"}
    secret = "test-secret"
    ok, token, metadata = _run(payload=payload, secret=secret)

    assert ok is True
    parts = token.split(".")
    assert len(parts) == 3
    assert metadata["algorithm"] == "HS256"

    header_raw = base64.urlsafe_b64decode(parts[0] + "==="[: (-len(parts[0])) % 4])
    assert json.loads(header_raw) == {"alg": "HS256", "typ": "JWT"}

    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    assert parts[2] == _b64url_bytes(expected_sig)


def test_jwt_encode_accepts_json_string_payload_and_optional_headers() -> None:
    """Payload may be a JSON string; headers merge with forced HS256 alg."""

    ok, token, _metadata = _run(
        payload='{"iss":"example"}',
        secret="key",
        headers={"kid": "kid-1", "alg": "none"},
    )

    assert ok is True
    parts = token.split(".")
    header_raw = base64.urlsafe_b64decode(parts[0] + "==="[: (-len(parts[0])) % 4])
    assert json.loads(header_raw) == {"alg": "HS256", "kid": "kid-1", "typ": "JWT"}

    decode_result = JwtDecodeTool().execute(ToolInvocation(tool_name="jwt_decode", arguments={"text": token}))
    assert decode_result.ok is True
    parsed = json.loads(decode_result.content)
    assert parsed["payload"] == {"iss": "example"}


def test_jwt_encode_rejects_missing_payload_and_secret() -> None:
    """Missing payload or secret fails structurally."""

    ok_payload, content_payload, _metadata = _run(secret="only-secret")
    ok_secret, content_secret, _metadata2 = _run(payload={"sub": "x"})

    assert ok_payload is False
    assert "missing required argument: payload" in content_payload
    assert ok_secret is False
    assert "missing required argument: secret" in content_secret


def test_jwt_encode_rejects_empty_secret_and_invalid_payload() -> None:
    """Empty secret and malformed payload are refused."""

    ok_empty, content_empty, _metadata = _run(payload={"sub": "x"}, secret="")
    ok_json, content_json, _metadata2 = _run(payload="not-json", secret="key")
    ok_array, content_array, _metadata3 = _run(payload="[1]", secret="key")

    assert ok_empty is False and "secret is empty" in content_empty
    assert ok_json is False and "invalid JSON payload" in content_json
    assert ok_array is False and "JSON object" in content_array


def test_jwt_encode_rejects_oversized_payload_and_secret() -> None:
    """Payload and secret size limits are enforced."""

    big_payload = {"data": "x" * 9_000}
    ok_payload, content_payload, metadata_payload = _run(payload=big_payload, secret="key")
    ok_secret, content_secret, metadata_secret = _run(payload={"sub": "x"}, secret="s" * 1_025)

    assert ok_payload is False
    assert "max_bytes" in content_payload
    payload_bytes = metadata_payload["payload_bytes"]
    assert isinstance(payload_bytes, int)
    assert payload_bytes > 8_192
    assert ok_secret is False
    assert "max_chars" in content_secret
    secret_chars = metadata_secret["secret_chars"]
    assert isinstance(secret_chars, int)
    assert secret_chars == 1_025


def test_jwt_encode_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "jwt_encode" in tools
    assert tools["jwt_encode"].name == "jwt_encode"
    SafetyPolicy().validate_tool("jwt_encode")
    assert "jwt_encode" in SafetyPolicy().allowed_tools
