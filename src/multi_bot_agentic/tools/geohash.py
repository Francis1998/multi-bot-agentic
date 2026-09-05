"""Geohash encode / decode tool for agent location pipelines.

Agents needing compact lat/lon identifiers often invent ad-hoc grid codes.
This tool encodes coordinates to geohash or decodes a geohash back to a
lat/lon center point with no network access. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_DEFAULT_MODE: Final[str] = "encode"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"encode", "decode"})
_MIN_PRECISION: Final[int] = 1
_MAX_PRECISION: Final[int] = 12
_DEFAULT_PRECISION: Final[int] = 7
_BASE32: Final[str] = "0123456789bcdefghjkmnpqrstuvwxyz"
_BASE32_INDEX: Final[dict[str, int]] = {ch: i for i, ch in enumerate(_BASE32)}
_BIT_MASKS: Final[tuple[int, ...]] = (16, 8, 4, 2, 1)


class GeohashTool:
    """Encode lat/lon to geohash or decode geohash to lat/lon."""

    name = "geohash"
    description = (
        "Encodes lat/lon to geohash or decodes geohash to lat/lon (mode encode|decode; precision 1..12); no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Encode coordinates or decode a geohash.

        Args:
            invocation: Tool invocation whose optional ``mode`` selects
                ``encode`` (default) or ``decode``. Encode reads ``lat``/
                ``lon`` (or ``latitude``/``longitude``) and optional
                ``precision``. Decode reads ``geohash`` / ``text`` / ``hash``.

        Returns:
            Tool result with a geohash string or ``lat,lon`` content;
            ``ok=False`` on errors.
        """

        mode = str(invocation.arguments.get("mode", _DEFAULT_MODE)).strip().lower()
        if mode not in _ALLOWED_MODES:
            supported = ", ".join(sorted(_ALLOWED_MODES))
            return self._fail(
                f"unsupported mode: {mode!r}; supported: {supported}",
                {"mode": mode},
            )

        if mode == "encode":
            return self._encode(invocation)
        return self._decode(invocation)

    def _encode(self, invocation: ToolInvocation) -> ToolResult:
        """Encode lat/lon into a geohash string."""

        raw_lat = invocation.arguments.get("lat")
        if raw_lat is None:
            raw_lat = invocation.arguments.get("latitude")
        raw_lon = invocation.arguments.get("lon")
        if raw_lon is None:
            raw_lon = invocation.arguments.get("longitude")
        if raw_lat is None or raw_lon is None:
            return self._fail(
                "missing required arguments: lat/lon (or latitude/longitude)",
                {"mode": "encode"},
            )
        try:
            lat = float(str(raw_lat).strip())
            lon = float(str(raw_lon).strip())
        except (TypeError, ValueError):
            return self._fail("lat and lon must be numeric", {"mode": "encode"})
        if not (-90.0 <= lat <= 90.0):
            return self._fail("lat out of range [-90, 90]", {"mode": "encode", "lat": lat})
        if not (-180.0 <= lon <= 180.0):
            return self._fail("lon out of range [-180, 180]", {"mode": "encode", "lon": lon})

        raw_precision = invocation.arguments.get("precision", _DEFAULT_PRECISION)
        try:
            precision = int(str(raw_precision).strip())
        except (TypeError, ValueError):
            return self._fail("precision must be an integer", {"mode": "encode"})
        if precision < _MIN_PRECISION or precision > _MAX_PRECISION:
            return self._fail(
                f"precision must be {_MIN_PRECISION}..{_MAX_PRECISION}",
                {"mode": "encode", "precision": precision},
            )

        value = _encode_geohash(lat, lon, precision)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=value,
            metadata={
                "mode": "encode",
                "lat": lat,
                "lon": lon,
                "precision": precision,
                "geohash": value,
            },
        )

    def _decode(self, invocation: ToolInvocation) -> ToolResult:
        """Decode a geohash string into lat/lon center point."""

        raw = invocation.arguments.get("geohash")
        if raw is None:
            raw = invocation.arguments.get("text")
        if raw is None:
            raw = invocation.arguments.get("hash")
        if raw is None:
            return self._fail(
                "missing required argument: geohash, text, or hash",
                {"mode": "decode"},
            )
        document = str(raw).strip().lower()
        if not document:
            return self._fail("geohash is empty", {"mode": "decode"})
        if len(document) < _MIN_PRECISION or len(document) > _MAX_PRECISION:
            return self._fail(
                f"geohash length must be {_MIN_PRECISION}..{_MAX_PRECISION}",
                {"mode": "decode", "chars": len(document)},
            )
        if any(ch not in _BASE32_INDEX for ch in document):
            return self._fail("geohash contains invalid characters", {"mode": "decode"})

        lat, lon = _decode_geohash(document)
        content = f"{lat},{lon}"
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "mode": "decode",
                "lat": lat,
                "lon": lon,
                "precision": len(document),
                "geohash": document,
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _encode_geohash(lat: float, lon: float, precision: int) -> str:
    """Encode latitude/longitude into a geohash of the given precision."""

    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    chars: list[str] = []
    bit = 0
    ch = 0
    even = True
    while len(chars) < precision:
        if even:
            mid = (lon_interval[0] + lon_interval[1]) / 2.0
            if lon >= mid:
                ch |= _BIT_MASKS[bit]
                lon_interval[0] = mid
            else:
                lon_interval[1] = mid
        else:
            mid = (lat_interval[0] + lat_interval[1]) / 2.0
            if lat >= mid:
                ch |= _BIT_MASKS[bit]
                lat_interval[0] = mid
            else:
                lat_interval[1] = mid
        even = not even
        if bit < 4:
            bit += 1
        else:
            chars.append(_BASE32[ch])
            bit = 0
            ch = 0
    return "".join(chars)


def _decode_geohash(geohash: str) -> tuple[float, float]:
    """Decode a geohash into the center latitude/longitude of its cell."""

    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    even = True
    for character in geohash:
        cd = _BASE32_INDEX[character]
        for mask in _BIT_MASKS:
            if even:
                mid = (lon_interval[0] + lon_interval[1]) / 2.0
                if cd & mask:
                    lon_interval[0] = mid
                else:
                    lon_interval[1] = mid
            else:
                mid = (lat_interval[0] + lat_interval[1]) / 2.0
                if cd & mask:
                    lat_interval[0] = mid
                else:
                    lat_interval[1] = mid
            even = not even
    lat = (lat_interval[0] + lat_interval[1]) / 2.0
    lon = (lon_interval[0] + lon_interval[1]) / 2.0
    return lat, lon
