"""Small stdlib JSON HTTP helper for provider adapters."""

from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen


def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    """POST JSON and decode the JSON response.

    Args:
        url: Target URL.
        payload: JSON-serializable request payload.
        headers: HTTP headers.
        timeout_seconds: Request timeout budget.

    Returns:
        Decoded JSON object.
    """

    request = Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", **headers},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("provider returned non-object JSON")
    return decoded
