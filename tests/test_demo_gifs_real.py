"""Guard: every GIF embedded in README/docs markdown is a real, renderable demo.

97 tool guides once embedded 1x1-pixel, 34-43 byte placeholder GIFs (plus two
undersized, corrupt ones), so readers saw nothing where a guide promised a
demo. This guard fails if an embedded GIF is missing, is not a structurally
valid GIF, is smaller than ``MIN_WIDTH`` x ``MIN_HEIGHT`` pixels, or is under
``MIN_BYTES``. Fix a failure by rendering a real demo; tool-guide demos come
from ``python scripts/render_guide_demos.py``, which runs the guide's python
example offline and draws the real output.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MIN_WIDTH = 200
MIN_HEIGHT = 100
MIN_BYTES = 2048

_FENCE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE = re.compile(r"(`+).+?\1")
_GIF_EMBED = re.compile(
    r"!\[[^\]]*\]\(\s*<?(?P<md>[^)\s>]+\.gif)>?[^)]*\)|<img\b[^>]*\bsrc=[\"'](?P<html>[^\"']+\.gif)[\"']",
    re.IGNORECASE,
)

# The 34-byte 1x1 placeholder that used to stand in for real demos.
PLACEHOLDER_1X1 = bytes.fromhex("47494638396101000100800000000000ffffff2c00000000010001000002014c003b")


def _markdown_files() -> list[Path]:
    """Return README plus every markdown file under docs/."""
    return sorted({ROOT / "README.md", *ROOT.glob("docs/**/*.md")})


def _gif_embeds() -> dict[Path, list[str]]:
    """Map each embedded local GIF path to the ``file:line`` locations embedding it.

    Image syntax inside fenced code blocks or inline code is an example, not an
    embed, so it is skipped; so are remote (``scheme://``) images.
    """
    embeds: dict[Path, list[str]] = {}
    for markdown in _markdown_files():
        in_fence = False
        for lineno, line in enumerate(markdown.read_text(encoding="utf-8").splitlines(), 1):
            if _FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in _GIF_EMBED.finditer(_INLINE_CODE.sub("", line)):
                target = match.group("md") or match.group("html")
                if "://" in target:
                    continue
                location = f"{markdown.relative_to(ROOT).as_posix()}:{lineno}"
                embeds.setdefault((markdown.parent / target).resolve(), []).append(location)
    return embeds


def _skip_sub_blocks(data: bytes, position: int) -> int:
    """Return the offset after a data sub-block chain, or -1 if it is truncated."""
    while position < len(data):
        size = data[position]
        position += 1
        if size == 0:
            return position
        position += size
    return -1


def _structure_problem(data: bytes) -> str | None:
    """Walk the GIF block structure and describe the first defect, if any."""
    packed = data[10]
    position = 13
    if packed & 0x80:
        position += 3 * (2 << (packed & 0x07))
    frames = 0
    while 0 <= position < len(data):
        introducer = data[position]
        if introducer == 0x3B:
            return None if frames else "no image frames"
        if introducer == 0x21:
            position = _skip_sub_blocks(data, position + 2)
        elif introducer == 0x2C:
            if position + 10 > len(data):
                return "truncated image descriptor"
            image_packed = data[position + 9]
            position += 10
            if image_packed & 0x80:
                position += 3 * (2 << (image_packed & 0x07))
            position = _skip_sub_blocks(data, position + 1)
            frames += 1
        else:
            return f"unexpected block 0x{introducer:02x} at byte {position}"
    return "truncated data sub-blocks" if position < 0 else "missing GIF trailer"


def gif_problems(data: bytes | None) -> list[str]:
    """Return why ``data`` is not a real demo GIF (empty list when it is one)."""
    if data is None:
        return ["missing file"]
    problems = []
    if len(data) < MIN_BYTES:
        problems.append(f"{len(data)} bytes < {MIN_BYTES}")
    if len(data) < 13 or data[:6] not in (b"GIF87a", b"GIF89a"):
        return [*problems, "not a GIF (bad signature or header)"]
    width, height = struct.unpack("<HH", data[6:10])
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        problems.append(f"{width}x{height} px < {MIN_WIDTH}x{MIN_HEIGHT}")
    structure = _structure_problem(data)
    if structure is not None:
        problems.append(structure)
    return problems


def test_scan_covers_readme_guides_and_catalogs() -> None:
    """The guard must actually see the README hero GIF and the guide demos."""
    locations = [location for found in _gif_embeds().values() for location in found]

    assert any(location.startswith("README.md:") for location in locations)
    assert any(location.startswith("docs/ADVISOR_CATALOG.md:") for location in locations)
    assert sum(location.startswith("docs/guides/") for location in locations) > 200


def _synthetic_gif(width: int, height: int) -> bytes:
    """Build a structurally valid one-frame GIF padded past ``MIN_BYTES`` by a comment."""
    comment = b"".join(b"\xff" + bytes(255) for _ in range(MIN_BYTES // 256 + 1))
    return b"".join(
        (
            b"GIF89a" + struct.pack("<HHBBB", width, height, 0, 0, 0),
            b"\x21\xfe" + comment + b"\x00",
            b"\x2c" + struct.pack("<HHHHB", 0, 0, width, height, 0) + b"\x02\x01\x4c\x00",
            b"\x3b",
        )
    )


def test_checker_flags_placeholders_and_corrupt_gifs() -> None:
    """The 1x1 placeholder, undersized or truncated GIFs, and missing files are rejected."""
    real = _synthetic_gif(480, 270)

    assert gif_problems(real) == []
    assert gif_problems(PLACEHOLDER_1X1) == ["34 bytes < 2048", "1x1 px < 200x100"]
    assert gif_problems(_synthetic_gif(160, 48)) == ["160x48 px < 200x100"]
    assert gif_problems(real[:-1]) == ["missing GIF trailer"]
    assert gif_problems(real[:MIN_BYTES]) == ["truncated data sub-blocks"]
    assert gif_problems(b"\x89PNG" + bytes(MIN_BYTES)) == ["not a GIF (bad signature or header)"]
    assert gif_problems(None) == ["missing file"]


def test_every_embedded_gif_is_a_real_demo() -> None:
    """Guides and catalogs must not embed missing, corrupt, or placeholder GIFs."""
    offenders = []
    for path, locations in sorted(_gif_embeds().items()):
        problems = gif_problems(path.read_bytes() if path.is_file() else None)
        if problems:
            shown = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
            offenders.append(f"{shown} ({', '.join(locations)}): {'; '.join(problems)}")

    assert offenders == [], (
        f"{len(offenders)} embedded GIF(s) are not real demos "
        "(render tool-guide demos with `python scripts/render_guide_demos.py`):\n" + "\n".join(offenders)
    )
