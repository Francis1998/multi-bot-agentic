"""Render a recorded terminal transcript as an animated GIF using pixel frames and ffmpeg.

This follows ``render_demo_gif.py`` (stdlib-only PPM frames stitched by ``ffmpeg``), but every
character it draws comes from a transcript of real command output: lines starting with ``$ ``
are typed, all other lines are printed exactly as captured. Glyphs are the public-domain X11
"misc-fixed" 8x13 font ("Public domain font.  Share and enjoy."), embedded below so the
rendering needs no font files or third-party packages.

Usage:
    python scripts/render_terminal_gif.py assets/demo/otel-trace-export.txt assets/demo/otel-trace-export.gif
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

Color = tuple[int, int, int]

# Palette shared with render_demo_gif.py.
BACKGROUND: Color = (7, 17, 31)
PANEL: Color = (11, 27, 49)
BLUE: Color = (96, 165, 250)
CYAN: Color = (103, 232, 249)
GREEN: Color = (187, 247, 208)
TEXT: Color = (224, 242, 254)
MUTED: Color = (147, 197, 253)
PALETTE: tuple[Color, ...] = (BACKGROUND, PANEL, BLUE, CYAN, GREEN, TEXT, MUTED)

GLYPH_WIDTH = 8
GLYPH_HEIGHT = 13
PADDING = 12
TITLE_HEIGHT = 24
# Lines printed by the CLI on stderr (notes and summaries) are drawn in the muted color.
MUTED_PREFIXES = ("note:", "exported ", "wrote ", "warning:", "error:", "mcp:")

# Printable ASCII glyphs: 13 rows per glyph, two hex digits (8 pixels, MSB = left) per row.
GLYPHS: dict[str, str] = {
    " ": "00000000000000000000000000",
    "!": "00001010101010101000100000",
    '"': "00002424240000000000000000",
    "#": "00000024247e247e2424000000",
    "$": "0000103c505038141478100000",
    "%": "0000225224080810242a440000",
    "&": "00000000304848304a443a0000",
    "'": "00001010100000000000000000",
    "(": "00000408081010100808040000",
    ")": "00002010100808081010200000",
    "*": "000024187e1824000000000000",
    "+": "0000000010107c101000000000",
    ",": "00000000000000000038304000",
    "-": "0000000000007c000000000000",
    ".": "00000000000000000010381000",
    "/": "00000202040810204080800000",
    "0": "00001824424242424224180000",
    "1": "000010305010101010107c0000",
    "2": "00003c424202041820407e0000",
    "3": "00007e0204081c0202423c0000",
    "4": "0000040c142444447e04040000",
    "5": "00007e40405c620202423c0000",
    "6": "00001c2040405c6242423c0000",
    "7": "00007e02040808101020200000",
    "8": "00003c4242423c4242423c0000",
    "9": "00003c4242463a020204380000",
    ":": "00000000103810000010381000",
    ";": "00000000103810000038304000",
    "<": "00000204081020100804020000",
    "=": "00000000007e00007e00000000",
    ">": "00004020100804081020400000",
    "?": "00003c42420204080800080000",
    "@": "00003c42424e52564a403c0000",
    "A": "000018244242427e4242420000",
    "B": "00007844424478444244780000",
    "C": "00003c424040404040423c0000",
    "D": "00007844424242424244780000",
    "E": "00007e404040784040407e0000",
    "F": "00007e40404078404040400000",
    "G": "00003c424040404e42463a0000",
    "H": "0000424242427e424242420000",
    "I": "00007c101010101010107c0000",
    "J": "00001f04040404040444380000",
    "K": "00004244485060504844420000",
    "L": "000040404040404040407e0000",
    "M": "00008282c6aa92928282820000",
    "N": "0000424262524a464242420000",
    "O": "00003c424242424242423c0000",
    "P": "00007c4242427c404040400000",
    "Q": "00003c4242424242524a3c0200",
    "R": "00007c4242427c504844420000",
    "S": "00003c4240403c0202423c0000",
    "T": "0000fe10101010101010100000",
    "U": "000042424242424242423c0000",
    "V": "00008282444444282828100000",
    "W": "000082828282929292aa440000",
    "X": "00008282442810284482820000",
    "Y": "00008282442810101010100000",
    "Z": "00007e020408102040407e0000",
    "[": "00003c202020202020203c0000",
    "\\": "00008080402010080402020000",
    "]": "00007808080808080808780000",
    "^": "00001028440000000000000000",
    "_": "0000000000000000000000fe00",
    "`": "00100800000000000000000000",
    "a": "00000000003c023e42463a0000",
    "b": "00004040405c624242625c0000",
    "c": "00000000003c424040423c0000",
    "d": "00000202023a464242463a0000",
    "e": "00000000003c427e40423c0000",
    "f": "00001c2220207c202020200000",
    "g": "00000000003a444438403c423c",
    "h": "00004040405c62424242420000",
    "i": "000000100030101010107c0000",
    "j": "00000004000c04040404444438",
    "k": "00004040404448704844420000",
    "l": "000030101010101010107c0000",
    "m": "0000000000ec92929292820000",
    "n": "00000000005c62424242420000",
    "o": "00000000003c424242423c0000",
    "p": "00000000005c6242625c404040",
    "q": "00000000003a4642463a020202",
    "r": "00000000005c22202020200000",
    "s": "00000000003c42300c423c0000",
    "t": "00000020207c202020221c0000",
    "u": "000000000044444444443a0000",
    "v": "00000000004444442828100000",
    "w": "000000000082829292aa440000",
    "x": "00000000004224181824420000",
    "y": "0000000000424242463a02423c",
    "z": "00000000007e040810207e0000",
    "{": "00000e101008300810100e0000",
    "|": "00001010101010101010100000",
    "}": "0000700808100c100808700000",
    "~": "00002454480000000000000000",
}


@dataclass(frozen=True)
class Frame:
    """One GIF frame: visible terminal lines and how long the frame is shown.

    Attributes:
        lines: Visible lines with their colors (already wrapped and scrolled).
        seconds: Display duration.
    """

    lines: tuple[tuple[str, Color], ...]
    seconds: float


def main() -> int:
    """Render the GIF.

    Returns:
        Process exit code.
    """

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("transcript", type=Path, help="transcript text file ($-prefixed lines are commands)")
    parser.add_argument("output", type=Path, help="GIF to write")
    parser.add_argument("--columns", type=int, default=100, help="terminal width in characters")
    parser.add_argument("--rows", type=int, default=32, help="terminal height in lines")
    parser.add_argument("--title", default="multi-bot-agentic", help="window title")
    args = parser.parse_args()

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise RuntimeError(f"ffmpeg is required to render {args.output}")
    transcript = args.transcript.read_text(encoding="utf-8").splitlines()
    frames = build_frames(transcript, columns=args.columns, rows=args.rows)
    width = args.columns * GLYPH_WIDTH + 2 * PADDING
    height = TITLE_HEIGHT + args.rows * GLYPH_HEIGHT + 2 * PADDING
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="multi-bot-agentic-gif-") as temporary_directory:
        directory = Path(temporary_directory)
        playlist = []
        for index, frame in enumerate(frames):
            path = directory / f"frame_{index:04d}.ppm"
            path.write_bytes(render_frame(frame, width=width, height=height, title=args.title))
            playlist.append(f"file '{path.name}'\nduration {frame.seconds:.2f}")
        # The concat demuxer ignores the last entry's duration unless the file is listed again.
        playlist.append(f"file 'frame_{len(frames) - 1:04d}.ppm'")
        (directory / "frames.txt").write_text("\n".join(playlist) + "\n", encoding="utf-8")
        palette = directory / "palette.ppm"
        palette.write_bytes(_ppm(16, 16, [list(PALETTE) + [BACKGROUND] * (256 - len(PALETTE))]))
        subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(directory / "frames.txt"),
                "-i",
                str(palette),
                "-lavfi",
                "[0:v][1:v]paletteuse=dither=none",
                "-fps_mode",
                "vfr",
                "-loop",
                "0",
                str(args.output),
            ],
            check=True,
        )
    print(f"wrote {args.output} ({len(frames)} frames, {args.output.stat().st_size // 1024} KiB)")
    return 0


def build_frames(transcript: list[str], *, columns: int, rows: int) -> list[Frame]:
    """Turn a transcript into typing, output, and pause frames.

    Args:
        transcript: Transcript lines; ``$ ``-prefixed lines are commands.
        columns: Terminal width.
        rows: Terminal height.

    Returns:
        Frames in display order.
    """

    screen: list[tuple[str, Color]] = []
    frames: list[Frame] = []

    def show(seconds: float, extra: list[tuple[str, Color]] | None = None) -> None:
        visible = (screen + (extra or []))[-rows:]
        frames.append(Frame(lines=tuple(visible), seconds=seconds))

    index = 0
    while index < len(transcript):
        line = transcript[index]
        if line.startswith("$ "):
            for typed in range(2, len(line) + 1, 6):
                show(0.04, [(segment, CYAN) for segment in wrap(line[:typed] + "_", columns)])
            show(0.5, [(segment, CYAN) for segment in wrap(line, columns)])
            screen.extend((segment, CYAN) for segment in wrap(line, columns))
            index += 1
            continue
        output: list[tuple[str, Color]] = []
        while index < len(transcript) and not transcript[index].startswith("$ "):
            text = transcript[index]
            color = MUTED if text.startswith(MUTED_PREFIXES) else TEXT
            output.extend((segment, color) for segment in wrap(text, columns))
            index += 1
        for start in range(0, len(output), 6):
            screen.extend(output[start : start + 6])
            show(0.06)
        last_command = index >= len(transcript)
        show(4.0 if last_command else 2.2)
    return frames


def wrap(line: str, columns: int) -> list[str]:
    """Soft-wrap ``line`` at ``columns`` characters, like a terminal does."""

    text = line.expandtabs(4)
    return [text[start : start + columns] for start in range(0, len(text), columns)] or [""]


def render_frame(frame: Frame, *, width: int, height: int, title: str) -> bytes:
    """Draw one frame as a binary PPM image."""

    pixels = [[BACKGROUND] * width for _ in range(height)]
    for y in range(TITLE_HEIGHT):
        pixels[y] = [PANEL] * width
    for dot, color in enumerate((BLUE, CYAN, GREEN)):
        _fill(pixels, PADDING + dot * 14, 8, 8, 8, color)
    _draw_text(pixels, title, PADDING + 48, 6, MUTED)
    for row, (text, color) in enumerate(frame.lines):
        _draw_text(pixels, text, PADDING, TITLE_HEIGHT + PADDING + row * GLYPH_HEIGHT, color)
    return _ppm(width, height, pixels)


def _draw_text(pixels: list[list[Color]], text: str, x: int, y: int, color: Color) -> None:
    """Draw ``text`` with the embedded font; characters outside printable ASCII draw as ``?``."""

    for column, character in enumerate(text):
        glyph = GLYPHS.get(character, GLYPHS["?"])
        left = x + column * GLYPH_WIDTH
        for row in range(GLYPH_HEIGHT):
            bits = int(glyph[2 * row : 2 * row + 2], 16)
            if not bits:
                continue
            line = pixels[y + row]
            for offset in range(GLYPH_WIDTH):
                if bits & (0x80 >> offset) and left + offset < len(line):
                    line[left + offset] = color


def _fill(pixels: list[list[Color]], x: int, y: int, width: int, height: int, color: Color) -> None:
    """Fill a rectangle."""

    for row in range(y, y + height):
        pixels[row][x : x + width] = [color] * width


def _ppm(width: int, height: int, pixels: list[list[Color]]) -> bytes:
    """Encode pixel rows as a binary PPM image."""

    rows = (bytes(channel for pixel in line for channel in pixel) for line in pixels)
    return f"P6\n{width} {height}\n255\n".encode("ascii") + b"".join(rows)


if __name__ == "__main__":
    raise SystemExit(main())
