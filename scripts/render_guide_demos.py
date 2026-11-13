"""Render terminal-transcript demo GIFs for docs guides from their real examples.

Tool guides embed a demo GIF from ``assets/demo/``. For every embedded GIF that is
missing or a placeholder (not a GIF, smaller than 200x100 px, or under 2 KB: the
thresholds ``tests/test_demo_gifs_real.py`` enforces) this script:

1. finds the markdown file that embeds it and takes its first python code block;
2. executes that block for real with ``sys.executable`` and ``PYTHONPATH=src``,
   under a timeout and with sockets disabled, so it cannot reach the network;
3. draws a terminal transcript (title bar, the example fed to ``python -`` as a
   heredoc, then the captured stdout) with the palette and pixel-font style of
   ``scripts/render_demo_gif.py``;
4. writes the GIF to the embedded path, so the markdown does not change.

Each GIF carries a comment naming its source guide. Re-rendering an explicitly
named guide only replaces placeholders and GIFs this script wrote; hand-made
demos (such as ``mcp-tools.gif``) need ``--force``. An example that fails or
prints nothing is a docs bug: it is reported and no GIF is written for it.

Only the standard library is needed (the script carries its own LZW GIF
encoder): no ffmpeg, no Pillow, no temporary files.

Usage::

    python scripts/render_guide_demos.py          # render every placeholder or missing GIF
    python scripts/render_guide_demos.py --list   # only list them (exit 1 if any)
    python scripts/render_guide_demos.py docs/guides/BASE58_TOOL_GUIDE.md  # re-render one guide
"""

from __future__ import annotations

import argparse
import builtins
import io
import keyword
import os
import re
import struct
import subprocess
import sys
import tokenize
import unicodedata
from dataclasses import dataclass
from math import isqrt
from pathlib import Path

from render_demo_gif import BACKGROUND, BLUE, CYAN, FONT, GREEN, MUTED, PANEL, TEXT, Color

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "assets" / "demo"

MIN_WIDTH = 200
MIN_HEIGHT = 100
MIN_BYTES = 2048

SCALE = 2
GLYPH_ROWS = 9
CELL_WIDTH = 6 * SCALE
CELL_HEIGHT = (GLYPH_ROWS + 1) * SCALE
WIDTH = 960
MARGIN = 12
TITLE_HEIGHT = 36
PADDING = 16
TEXT_LEFT = MARGIN + PADDING
TEXT_TOP = MARGIN + TITLE_HEIGHT + PADDING
COLUMNS = (WIDTH - 2 * TEXT_LEFT) // CELL_WIDTH
MIN_ROWS = 10
MAX_ROWS = 40
CODE_DELAY_CS = 160
OUTPUT_DELAY_CS = 480
EXAMPLE_TIMEOUT_SECONDS = 60.0

TITLE_BAR = (16, 38, 66)
DIM = (71, 105, 145)
DOT_RED = (248, 113, 113)
DOT_AMBER = (251, 191, 36)
DOT_GREEN = (74, 222, 128)
PALETTE: tuple[Color, ...] = (
    BACKGROUND,
    PANEL,
    TITLE_BAR,
    BLUE,
    CYAN,
    GREEN,
    TEXT,
    MUTED,
    DIM,
    DOT_RED,
    DOT_AMBER,
    DOT_GREEN,
)
INK = {color: index for index, color in enumerate(PALETTE)}
LZW_MIN_CODE_SIZE = 4
PROVENANCE = "Rendered by scripts/render_guide_demos.py from "

# Lowercase letters and punctuation in the 5-pixel-wide style of render_demo_gif.FONT.
# Rows 0-6 hold the body (capitals are 7 rows tall, x-height is rows 2-6);
# rows 7-8 hold descenders. Glyphs with fewer rows are padded with blank rows.
# ``|`` replaces FONT's version with a taller bar so it does not read as ``l``.
EXTRA_GLYPHS: dict[str, tuple[str, ...]] = {
    "a": ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    "b": ("10000", "10000", "10110", "11001", "10001", "10001", "11110"),
    "c": ("00000", "00000", "01110", "10000", "10000", "10001", "01110"),
    "d": ("00001", "00001", "01101", "10011", "10001", "10001", "01111"),
    "e": ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    "f": ("00110", "01001", "01000", "11100", "01000", "01000", "01000"),
    "g": ("00000", "00000", "01111", "10001", "10001", "10001", "01111", "00001", "01110"),
    "h": ("10000", "10000", "10110", "11001", "10001", "10001", "10001"),
    "i": ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    "j": ("00010", "00000", "00110", "00010", "00010", "00010", "00010", "10010", "01100"),
    "k": ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    "l": ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    "m": ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    "n": ("00000", "00000", "10110", "11001", "10001", "10001", "10001"),
    "o": ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    "p": ("00000", "00000", "11110", "10001", "10001", "10001", "11110", "10000", "10000"),
    "q": ("00000", "00000", "01111", "10001", "10001", "10001", "01111", "00001", "00001"),
    "r": ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    "s": ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    "t": ("01000", "01000", "11100", "01000", "01000", "01001", "00110"),
    "u": ("00000", "00000", "10001", "10001", "10001", "10011", "01101"),
    "v": ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    "w": ("00000", "00000", "10001", "10001", "10101", "10101", "01010"),
    "x": ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    "y": ("00000", "00000", "10001", "10001", "10001", "10001", "01111", "00001", "01110"),
    "z": ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    '"': ("01010", "01010", "01010", "00000", "00000", "00000", "00000"),
    "#": ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    "%": ("11000", "11001", "00010", "00100", "01000", "10011", "00011"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "*": ("00000", "00100", "10101", "01110", "10101", "00100", "00000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    ",": ("00000", "00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    "/": ("00000", "00001", "00010", "00100", "01000", "10000", "00000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ";": ("00000", "01100", "01100", "00000", "01100", "01100", "00100", "01000"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    "@": ("01110", "10001", "00001", "01101", "10101", "10101", "01110"),
    "[": ("01110", "01000", "01000", "01000", "01000", "01000", "01110"),
    "\\": ("00000", "10000", "01000", "00100", "00010", "00001", "00000"),
    "]": ("01110", "00010", "00010", "00010", "00010", "00010", "01110"),
    "^": ("00100", "01010", "10001", "00000", "00000", "00000", "00000"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "`": ("01000", "00100", "00010", "00000", "00000", "00000", "00000"),
    "{": ("00110", "00100", "00100", "01000", "00100", "00100", "00110"),
    "}": ("01100", "00100", "00100", "00010", "00100", "00100", "01100"),
    "|": ("00100",) * GLYPH_ROWS,
    "~": ("00000", "00000", "01000", "10101", "00010", "00000", "00000"),
    "·": ("00000", "00000", "00000", "00100", "00000", "00000", "00000"),
    "…": ("00000", "00000", "00000", "00000", "00000", "00000", "10101"),
}
GLYPHS = {
    character: rows + ("00000",) * (GLYPH_ROWS - len(rows)) for character, rows in {**FONT, **EXTRA_GLYPHS}.items()
}
# Combining marks drawn over a lowercase base letter: (first row, rows).
ACCENTS: dict[str, tuple[int, tuple[str, ...]]] = {
    "\u0300": (0, ("01000", "00100")),
    "\u0301": (0, ("00010", "00100")),
    "\u0302": (0, ("00100", "01010")),
    "\u0303": (0, ("01101", "10010")),
    "\u0308": (0, ("01010", "00000")),
    "\u0327": (7, ("00100", "01000")),
}
# (row, column) of Braille dots 1-8, i.e. bits 0-7 of the pattern after U+2800.
BRAILLE_DOTS = ((0, 1), (2, 1), (4, 1), (0, 3), (2, 3), (4, 3), (6, 1), (6, 3))
BREAK_AFTER = frozenset(" ,;(")
BUILTIN_NAMES = frozenset(name for name in dir(builtins) if not name.startswith("_"))

FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"(`+).+?\1")
GIF_EMBED = re.compile(
    r"!\[[^\]]*\]\(\s*<?(?P<md>[^)\s>]+\.gif)>?[^)]*\)|<img\b[^>]*\bsrc=[\"'](?P<html>[^\"']+\.gif)[\"']",
    re.IGNORECASE,
)
PYTHON_BLOCK = re.compile(r"^```python[ \t]*\n(?P<code>.*?)^```", re.MULTILINE | re.DOTALL)

# Runs inside the example's interpreter: disable sockets, then exec the example from stdin.
RUNNER = """\
import socket
import sys


def _offline(*args, **kwargs):
    raise OSError("network access is disabled while rendering guide demos")


socket.socket.connect = socket.socket.connect_ex = _offline
socket.create_connection = socket.getaddrinfo = _offline
source = sys.stdin.read()
exec(compile(source, sys.argv[1], "exec"), {"__name__": "__main__"})
"""

Cell = tuple[str, Color]


class DemoError(Exception):
    """A guide demo cannot be rendered (broken example, unknown glyph, bad link)."""


@dataclass(frozen=True)
class Demo:
    """One embedded GIF and the markdown file whose python example it shows."""

    gif: Path
    guide: Path


@dataclass(frozen=True)
class Frame:
    """A GIF frame: a palette-index rectangle drawn at ``(left, top)``."""

    left: int
    top: int
    width: int
    height: int
    pixels: bytes
    delay_cs: int


def relative(path: Path) -> str:
    """Return ``path`` relative to the repository root when possible."""
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def glyph_rows(character: str) -> tuple[str, ...]:
    """Return the 5x9 bitmap rows for ``character``.

    Raises:
        DemoError: If no glyph exists, so a demo never silently drops text.
    """
    if character in GLYPHS:
        return GLYPHS[character]
    code_point = ord(character)
    if 0x2800 <= code_point <= 0x28FF:
        dots = [["0"] * 5 for _ in range(GLYPH_ROWS)]
        for bit, (row, column) in enumerate(BRAILLE_DOTS):
            if (code_point - 0x2800) >> bit & 1:
                dots[row][column] = "1"
        return tuple("".join(row) for row in dots)
    decomposed = unicodedata.normalize("NFD", character)
    base, marks = decomposed[0], decomposed[1:]
    if base.islower() and base in GLYPHS and marks and all(mark in ACCENTS for mark in marks):
        rows = list(GLYPHS[base])
        if base in "ij":
            rows[0] = "00000"
        for mark in marks:
            first_row, accent = ACCENTS[mark]
            for offset, accent_row in enumerate(accent):
                merged = int(rows[first_row + offset], 2) | int(accent_row, 2)
                rows[first_row + offset] = f"{merged:05b}"
        return tuple(rows)
    raise DemoError(f"no glyph for {character!r} (U+{code_point:04X}); add one to EXTRA_GLYPHS")


def markdown_files() -> list[Path]:
    """Return README plus every markdown file under docs/ (what the guard scans)."""
    return sorted({ROOT / "README.md", *ROOT.glob("docs/**/*.md")})


def gif_embeds() -> dict[Path, list[Path]]:
    """Map each locally embedded GIF to the markdown files embedding it (code is skipped)."""
    embeds: dict[Path, list[Path]] = {}
    for markdown in markdown_files():
        in_fence = False
        for line in markdown.read_text(encoding="utf-8").splitlines():
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in GIF_EMBED.finditer(INLINE_CODE.sub("", line)):
                target = match.group("md") or match.group("html")
                if "://" not in target:
                    sources = embeds.setdefault((markdown.parent / target).resolve(), [])
                    if markdown not in sources:
                        sources.append(markdown)
    return embeds


def is_placeholder(path: Path) -> bool:
    """Return True if ``path`` is missing, not a GIF, under 2 KB, or under 200x100 px."""
    if not path.is_file():
        return True
    data = path.read_bytes()
    if len(data) < MIN_BYTES or data[:6] not in (b"GIF87a", b"GIF89a"):
        return True
    width, height = struct.unpack("<HH", data[6:10])
    return bool(width < MIN_WIDTH or height < MIN_HEIGHT)


def is_generated(path: Path) -> bool:
    """Return True if ``path`` is a GIF this script wrote (it carries the provenance comment)."""
    return path.is_file() and PROVENANCE.encode("ascii") in path.read_bytes()


def first_python_block(markdown: Path) -> str | None:
    """Return the first ```python block of ``markdown``, or None if it has none."""
    match = PYTHON_BLOCK.search(markdown.read_text(encoding="utf-8"))
    return match.group("code").rstrip("\n") if match else None


def find_demos(guides: list[Path], force: bool = False) -> list[Demo]:
    """Return the demos to render: those of ``guides``, or every placeholder/missing GIF.

    Raises:
        DemoError: If a requested guide is missing or embeds no GIF, a requested
            GIF is a hand-made demo (unless ``force``), or a GIF would be written
            outside ``assets/demo/`` (which means the embed link is broken).
    """
    embeds = gif_embeds()
    demos: list[Demo] = []
    if guides:
        for guide in (path.resolve() for path in guides):
            if not guide.is_file():
                raise DemoError(f"{relative(guide)}: no such file")
            found = [Demo(gif, guide) for gif, sources in sorted(embeds.items()) if guide in sources]
            if not found:
                raise DemoError(f"{relative(guide)} embeds no local GIF")
            for demo in found:
                if not (force or is_placeholder(demo.gif) or is_generated(demo.gif)):
                    raise DemoError(f"{relative(demo.gif)} is a hand-made demo; pass --force to replace it")
            demos.extend(found)
    else:
        for gif, sources in sorted(embeds.items()):
            if is_placeholder(gif):
                with_example = [source for source in sources if first_python_block(source) is not None]
                demos.append(Demo(gif, (with_example or sources)[0]))
    for demo in demos:
        if not demo.gif.is_relative_to(DEMO_DIR):
            raise DemoError(f"{relative(demo.guide)} embeds {relative(demo.gif)}, outside assets/demo/; broken link?")
    return demos


def run_example(source: str, label: str, timeout: float) -> str:
    """Execute a guide's python example offline and return its stdout.

    Raises:
        DemoError: If the example fails or prints nothing (both are docs bugs).
    """
    env = {
        **os.environ,
        "PYTHONPATH": "src",
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TZ": "UTC",
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-c", RUNNER, label],
            input=source,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            cwd=ROOT,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise DemoError(f"{label}: example timed out after {timeout:g}s") from error
    if completed.returncode != 0:
        last_line = (completed.stderr.strip().splitlines() or ["(no stderr)"])[-1]
        raise DemoError(f"{label}: example exited {completed.returncode}: {last_line}")
    if not completed.stdout.strip():
        raise DemoError(f"{label}: example printed nothing; print the result so the demo shows it")
    return completed.stdout


def highlight(source: str) -> list[list[Cell]]:
    """Split ``source`` into lines of (character, color) cells with light syntax colors."""
    lines = source.split("\n")
    colors: list[list[Color]] = [[TEXT] * len(line) for line in lines]
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source + "\n").readline))
    except (tokenize.TokenError, SyntaxError):
        tokens = []
    for token in tokens:
        kind = tokenize.tok_name[token.type]
        color: Color | None = None
        if kind == "COMMENT":
            color = MUTED
        elif kind == "STRING" or kind.startswith("FSTRING"):
            color = GREEN
        elif kind == "NUMBER":
            color = CYAN
        elif kind == "NAME" and (keyword.iskeyword(token.string) or token.string in BUILTIN_NAMES):
            color = BLUE
        if color is None:
            continue
        (start_row, start_column), (end_row, end_column) = token.start, token.end
        for row in range(start_row, min(end_row, len(lines)) + 1):
            first = start_column if row == start_row else 0
            last = end_column if row == end_row else len(lines[row - 1])
            colors[row - 1][first:last] = [color] * (last - first)
    return [list(zip(line, line_colors, strict=True)) for line, line_colors in zip(lines, colors, strict=True)]


def expand_tabs(cells: list[Cell], tab_size: int = 8) -> list[Cell]:
    """Expand tab cells to spaces at terminal tab stops."""
    expanded: list[Cell] = []
    for character, color in cells:
        if character == "\t":
            expanded.extend([(" ", color)] * (tab_size - len(expanded) % tab_size))
        else:
            expanded.append((character, color))
    return expanded


def wrap(
    cells: list[Cell], width: int, prefix: list[Cell], continuation: list[Cell], hanging: int = 0
) -> list[list[Cell]]:
    """Wrap one logical line into rows of at most ``width`` cells after the prefix.

    Rows break after a space, comma, semicolon, or opening parenthesis in their
    right half when possible (otherwise mid-word, like a terminal), and
    continuation rows are indented by ``hanging`` extra cells.
    """
    cells = expand_tabs(cells)
    rows: list[list[Cell]] = []
    limit = width
    while len(cells) > limit:
        cut = next((index for index in range(limit, limit // 2, -1) if cells[index - 1][0] in BREAK_AFTER), limit)
        rows.append(cells[:cut])
        cells = cells[cut:]
        while len(cells) > 1 and cells[0][0] == " " and cut < limit:
            cells = cells[1:]
        limit = width - hanging
    rows.append(cells)
    indent = plain(" " * hanging, TEXT)
    return [prefix + row if index == 0 else continuation + indent + row for index, row in enumerate(rows)]


def plain(text: str, color: Color) -> list[Cell]:
    """Return ``text`` as cells of a single color."""
    return [(character, color) for character in text]


def transcript(source: str, output: str) -> tuple[list[list[Cell]], int]:
    """Lay out the terminal session as rows of cells.

    Returns:
        The rows, and the index of the first row that only appears once the
        example has run (its stdout and the next prompt).

    Raises:
        DemoError: If the example alone does not fit in ``MAX_ROWS`` rows.
    """
    heredoc_prompt = plain("> ", DIM)
    rows = [plain("$ ", CYAN) + plain("PYTHONPATH=src python - <<'EOF'", TEXT)]
    for code_line in highlight(source):
        indent = len(code_line) - len("".join(character for character, _ in code_line).lstrip(" "))
        rows.extend(wrap(code_line, COLUMNS - 2, heredoc_prompt, plain("  ", DIM), min(indent + 4, COLUMNS // 3)))
    rows.append(heredoc_prompt + plain("EOF", DIM))
    first_output_row = len(rows)
    if first_output_row + 2 > MAX_ROWS:
        raise DemoError(f"example needs {first_output_row} rows; keep guide examples under {MAX_ROWS - 2}")
    output_rows: list[list[Cell]] = []
    lines = output.replace("\r\n", "\n").split("\n")
    if lines[-1] == "":
        lines.pop()
    for line in lines:
        output_rows.extend(wrap(plain(line, TEXT), COLUMNS, [], []))
    room = MAX_ROWS - first_output_row - 1
    if len(output_rows) > room:
        hidden = len(output_rows) - room + 1
        output_rows = [*output_rows[: room - 1], plain(f"… {hidden} more output rows", DIM)]
    return [*rows, *output_rows, plain("$ ", CYAN)], first_output_row


class Canvas:
    """A palette-indexed pixel buffer."""

    def __init__(self, width: int, height: int, color: Color) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray([INK[color]]) * (width * height)

    def copy(self) -> Canvas:
        """Return an independent copy of this canvas."""
        clone = Canvas(self.width, self.height, BACKGROUND)
        clone.pixels[:] = self.pixels
        return clone

    def fill_rect(self, left: int, top: int, width: int, height: int, color: Color) -> None:
        """Fill a rectangle, clipped to the canvas."""
        x_start, x_end = max(0, left), min(self.width, left + width)
        if x_start >= x_end:
            return
        run = bytes([INK[color]]) * (x_end - x_start)
        for y_value in range(max(0, top), min(self.height, top + height)):
            offset = y_value * self.width + x_start
            self.pixels[offset : offset + len(run)] = run

    def outline(self, left: int, top: int, width: int, height: int, color: Color) -> None:
        """Draw a one-pixel rectangle outline."""
        self.fill_rect(left, top, width, 1, color)
        self.fill_rect(left, top + height - 1, width, 1, color)
        self.fill_rect(left, top, 1, height, color)
        self.fill_rect(left + width - 1, top, 1, height, color)

    def disc(self, center_x: int, center_y: int, radius: int, color: Color) -> None:
        """Fill a circle."""
        for offset in range(-radius, radius + 1):
            half = isqrt(radius * radius - offset * offset)
            self.fill_rect(center_x - half, center_y + offset, 2 * half + 1, 1, color)

    def text(self, left: int, top: int, cells: list[Cell]) -> None:
        """Draw cells with the pixel font at ``SCALE``."""
        for index, (character, color) in enumerate(cells):
            x_origin = left + index * CELL_WIDTH
            for row_index, row in enumerate(glyph_rows(character)):
                for column_index, bit in enumerate(row):
                    if bit == "1":
                        self.fill_rect(x_origin + column_index * SCALE, top + row_index * SCALE, SCALE, SCALE, color)


def draw_window(canvas: Canvas, title: str) -> None:
    """Draw the terminal window chrome: panel, title bar, traffic lights, title."""
    window_width, window_height = canvas.width - 2 * MARGIN, canvas.height - 2 * MARGIN
    canvas.fill_rect(MARGIN, MARGIN, window_width, window_height, PANEL)
    canvas.fill_rect(MARGIN, MARGIN, window_width, TITLE_HEIGHT, TITLE_BAR)
    canvas.outline(MARGIN, MARGIN, window_width, window_height, BLUE)
    canvas.fill_rect(MARGIN, MARGIN + TITLE_HEIGHT, window_width, 1, BLUE)
    center_y = MARGIN + TITLE_HEIGHT // 2
    for index, color in enumerate((DOT_RED, DOT_AMBER, DOT_GREEN)):
        canvas.disc(MARGIN + 20 + 20 * index, center_y, 6, color)
    title_left = MARGIN + 84
    title_columns = (canvas.width - MARGIN - PADDING - title_left) // CELL_WIDTH
    badge = "real run · offline"
    text_top = center_y - 7 * SCALE // 2
    canvas.text(title_left, text_top, plain(title[:title_columns], MUTED))
    if len(title) + 2 + len(badge) <= title_columns:
        canvas.text(title_left + (title_columns - len(badge)) * CELL_WIDTH, text_top, plain(badge, DIM))


def draw_rows(canvas: Canvas, rows: list[list[Cell]], first: int) -> None:
    """Draw transcript rows starting at row index ``first``."""
    for index in range(first, len(rows)):
        canvas.text(TEXT_LEFT, TEXT_TOP + index * CELL_HEIGHT, rows[index])


def changed_region(before: Canvas, after: Canvas) -> tuple[int, int, int, int]:
    """Return ``(left, top, width, height)`` of the pixels that differ (at least 1x1)."""
    width = after.width
    rows = [
        (before.pixels[y_value * width : (y_value + 1) * width], after.pixels[y_value * width : (y_value + 1) * width])
        for y_value in range(after.height)
    ]
    changed = [y_value for y_value, (old, new) in enumerate(rows) if old != new]
    if not changed:
        return 0, 0, 1, 1
    left, right = width - 1, 0
    for y_value in changed:
        old, new = rows[y_value]
        left = min(left, next(x for x in range(width) if old[x] != new[x]))
        right = max(right, next(x for x in range(width - 1, -1, -1) if old[x] != new[x]))
    return left, changed[0], right - left + 1, changed[-1] - changed[0] + 1


def crop(canvas: Canvas, left: int, top: int, width: int, height: int, delay_cs: int) -> Frame:
    """Cut a frame rectangle out of ``canvas``."""
    pixels = b"".join(
        canvas.pixels[(top + row) * canvas.width + left : (top + row) * canvas.width + left + width]
        for row in range(height)
    )
    return Frame(left, top, width, height, pixels, delay_cs)


def render_frames(title: str, source: str, output: str) -> tuple[int, int, list[Frame]]:
    """Render the example frame, then the output frame as a delta over it.

    Returns:
        Canvas width, canvas height, and the GIF frames.
    """
    rows, first_output_row = transcript(source, output)
    height = 2 * (MARGIN + PADDING) + TITLE_HEIGHT + max(MIN_ROWS, len(rows)) * CELL_HEIGHT
    example = Canvas(WIDTH, height, BACKGROUND)
    draw_window(example, title)
    draw_rows(example, rows[:first_output_row], 0)
    finished = example.copy()
    draw_rows(finished, rows, first_output_row)
    cursor_left = TEXT_LEFT + len(rows[-1]) * CELL_WIDTH
    finished.fill_rect(cursor_left, TEXT_TOP + (len(rows) - 1) * CELL_HEIGHT, 5 * SCALE, GLYPH_ROWS * SCALE, TEXT)
    return (
        WIDTH,
        height,
        [
            crop(example, 0, 0, WIDTH, height, CODE_DELAY_CS),
            crop(finished, *changed_region(example, finished), OUTPUT_DELAY_CS),
        ],
    )


def lzw_compress(pixels: bytes, min_code_size: int) -> bytes:
    """Compress palette indices with GIF's variable-width LZW (LSB-first codes)."""
    clear_code = 1 << min_code_size
    end_code = clear_code + 1
    code_size = min_code_size + 1
    next_code = end_code + 1
    table: dict[int, int] = {}
    packed = bytearray()
    buffer, bits = clear_code, code_size
    prefix = pixels[0]
    for pixel in pixels[1:]:
        key = prefix << 8 | pixel
        code = table.get(key)
        if code is not None:
            prefix = code
            continue
        buffer |= prefix << bits
        bits += code_size
        if next_code < 4096:
            table[key] = next_code
            if next_code == 1 << code_size and code_size < 12:
                code_size += 1
            next_code += 1
        else:
            buffer |= clear_code << bits
            bits += code_size
            table.clear()
            code_size = min_code_size + 1
            next_code = end_code + 1
        while bits >= 8:
            packed.append(buffer & 0xFF)
            buffer >>= 8
            bits -= 8
        prefix = pixel
    buffer |= prefix << bits
    bits += code_size
    # The decoder widens its codes after reading the final code, before the end code.
    if next_code == 1 << code_size and code_size < 12:
        code_size += 1
    buffer |= end_code << bits
    bits += code_size
    while bits > 0:
        packed.append(buffer & 0xFF)
        buffer >>= 8
        bits -= 8
    return bytes(packed)


def encode_gif(width: int, height: int, frames: list[Frame], comment: str) -> bytes:
    """Encode looping GIF89a frames that share the global ``PALETTE``, plus a comment."""
    color_table = b"".join(bytes(color) for color in PALETTE).ljust(3 << (LZW_MIN_CODE_SIZE), b"\x00")
    table_size_bits = LZW_MIN_CODE_SIZE - 1
    gif = bytearray(b"GIF89a")
    gif += struct.pack("<HHBBB", width, height, 0xF0 | table_size_bits, 0, 0)
    gif += color_table
    gif += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    note = comment.encode("ascii", "replace")[:255]
    gif += b"\x21\xfe" + bytes([len(note)]) + note + b"\x00"
    for frame in frames:
        gif += struct.pack("<BBBBHBB", 0x21, 0xF9, 4, 0x04, frame.delay_cs, 0, 0)
        gif += struct.pack("<BHHHHB", 0x2C, frame.left, frame.top, frame.width, frame.height, 0)
        gif.append(LZW_MIN_CODE_SIZE)
        data = lzw_compress(frame.pixels, LZW_MIN_CODE_SIZE)
        for start in range(0, len(data), 255):
            chunk = data[start : start + 255]
            gif.append(len(chunk))
            gif += chunk
        gif.append(0)
    gif.append(0x3B)
    return bytes(gif)


def render_demo(demo: Demo, timeout: float) -> tuple[bytes, int, int]:
    """Run the demo's example and return the encoded GIF with its width and height."""
    source = first_python_block(demo.guide)
    if source is None:
        raise DemoError(f"{relative(demo.guide)} has no ```python example to run")
    output = run_example(source, relative(demo.guide), timeout)
    width, height, frames = render_frames(relative(demo.guide), source, output)
    return encode_gif(width, height, frames, PROVENANCE + relative(demo.guide)), width, height


def main(argv: list[str] | None = None) -> int:
    """Render (or list) guide demo GIFs.

    Returns:
        0 on success; 1 if any demo failed (or, with ``--list``, if any is
        pending); 2 for usage errors.
    """
    parser = argparse.ArgumentParser(description="Render guide demo GIFs from their real python examples.")
    parser.add_argument(
        "guides",
        nargs="*",
        type=Path,
        help="markdown files whose embedded GIFs to re-render (default: every placeholder or missing GIF)",
    )
    parser.add_argument("--list", action="store_true", help="only list the GIFs that would be rendered")
    parser.add_argument("--force", action="store_true", help="also replace hand-made GIFs of the given guides")
    parser.add_argument("--timeout", type=float, default=EXAMPLE_TIMEOUT_SECONDS, help="seconds per example")
    args = parser.parse_args(argv)
    try:
        demos = find_demos(args.guides, args.force)
    except DemoError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.list:
        for demo in demos:
            print(f"{relative(demo.gif)} <- {relative(demo.guide)}")
        return 1 if demos else 0
    if not demos:
        print("every embedded GIF is already a real demo")
    failures = 0
    for demo in demos:
        try:
            data, width, height = render_demo(demo, args.timeout)
        except DemoError as error:
            failures += 1
            print(f"FAILED {relative(demo.gif)}: {error}", file=sys.stderr)
            continue
        demo.gif.write_bytes(data)
        print(f"rendered {relative(demo.gif)} ({width}x{height}, {len(data):,} bytes) from {relative(demo.guide)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
