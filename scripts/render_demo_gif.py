"""Render a small terminal-style GIF intro using ffmpeg and pixel frames."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

Color = tuple[int, int, int]

WIDTH = 480
HEIGHT = 270
BACKGROUND = (7, 17, 31)
PANEL = (11, 27, 49)
BLUE = (96, 165, 250)
CYAN = (103, 232, 249)
GREEN = (187, 247, 208)
TEXT = (224, 242, 254)
MUTED = (147, 197, 253)

FONT: dict[str, tuple[str, ...]] = {
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "$": ("01110", "10100", "10100", "01110", "00101", "00101", "11110"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ">": ("10000", "01000", "00100", "00010", "00100", "01000", "10000"),
    "|": ("00100", "00100", "00100", "00100", "00100", "00100", "00100"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00001", "00001", "00001", "00001", "10001", "10001", "01110"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}


def main() -> int:
    """Render the demo GIF.

    Returns:
        Process exit code.
    """

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise RuntimeError("ffmpeg is required to render docs/demo.gif")

    output_path = Path("docs/demo.gif")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="multi-bot-agentic-gif-") as temporary_directory:
        frame_directory = Path(temporary_directory)
        render_frames(frame_directory)
        subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-framerate",
                "8",
                "-i",
                str(frame_directory / "frame_%03d.ppm"),
                "-vf",
                "scale=480:270:flags=neighbor",
                "-loop",
                "0",
                str(output_path),
            ],
            check=True,
        )
    return 0


def render_frames(frame_directory: Path) -> None:
    """Render all PPM frames for the GIF.

    Args:
        frame_directory: Directory where frame files are written.
    """

    for frame_index in range(64):
        pixels = new_canvas()
        draw_rect(pixels, 18, 17, 444, 236, PANEL)
        draw_rect_outline(pixels, 18, 17, 444, 236, BLUE)
        draw_text(pixels, "MULTI BOT AGENTIC", 32, 35, TEXT, 3)
        draw_text(pixels, "OBSERVE > DECIDE > ACT > REPLAY", 34, 68, MUTED, 2)
        draw_stage_cards(pixels)
        draw_terminal(pixels, frame_index)
        write_ppm(frame_directory / f"frame_{frame_index:03d}.ppm", pixels)


def new_canvas() -> list[list[Color]]:
    """Create a blank canvas.

    Returns:
        Pixel matrix.
    """

    return [[BACKGROUND for _ in range(WIDTH)] for _ in range(HEIGHT)]


def draw_stage_cards(pixels: list[list[Color]]) -> None:
    """Draw the four ODA stage cards.

    Args:
        pixels: Pixel matrix to modify.
    """

    cards = (
        ("OBSERVE", 38, (23, 59, 103)),
        ("DECIDE", 146, (18, 57, 95)),
        ("ACT", 254, (15, 74, 103)),
        ("REPLAY", 362, (8, 47, 73)),
    )
    for title, x_position, color in cards:
        draw_rect(pixels, x_position, 96, 80, 42, color)
        draw_rect_outline(pixels, x_position, 96, 80, 42, CYAN)
        draw_text(pixels, title, x_position + 10, 110, TEXT, 1)


def draw_terminal(pixels: list[list[Color]], frame_index: int) -> None:
    """Draw the animated terminal section.

    Args:
        pixels: Pixel matrix to modify.
        frame_index: Current frame index.
    """

    draw_rect(pixels, 34, 158, 412, 74, (2, 6, 23))
    draw_rect_outline(pixels, 34, 158, 412, 74, BLUE)
    progress_x = 42 + int((frame_index % 32) * 360 / 31)
    draw_rect(pixels, progress_x, 148, 18, 4, CYAN)
    lines = [
        "$ RUN PROVIDER FAKE",
        "STATE SUCCEEDED | STEPS 4",
        "RULE MODEL REQUESTED TOOL",
        "EVENT LOG REPLAY READY",
    ]
    for line_index, line in enumerate(lines):
        if frame_index >= line_index * 10:
            draw_text(pixels, line, 48, 172 + line_index * 14, GREEN if line_index == 1 else TEXT, 1)


def draw_text(
    pixels: list[list[Color]],
    text: str,
    x_position: int,
    y_position: int,
    color: Color,
    scale: int,
) -> None:
    """Draw pixel-font text.

    Args:
        pixels: Pixel matrix to modify.
        text: Text to draw.
        x_position: Horizontal position.
        y_position: Vertical position.
        color: Text color.
        scale: Pixel scale.
    """

    cursor_x = x_position
    for character in text.upper():
        glyph = FONT.get(character, FONT[" "])
        for row_index, row in enumerate(glyph):
            for column_index, value in enumerate(row):
                if value == "1":
                    draw_rect(
                        pixels,
                        cursor_x + column_index * scale,
                        y_position + row_index * scale,
                        scale,
                        scale,
                        color,
                    )
        cursor_x += 6 * scale


def draw_rect(
    pixels: list[list[Color]],
    x_position: int,
    y_position: int,
    width: int,
    height: int,
    color: Color,
) -> None:
    """Draw a filled rectangle.

    Args:
        pixels: Pixel matrix to modify.
        x_position: Horizontal position.
        y_position: Vertical position.
        width: Rectangle width.
        height: Rectangle height.
        color: Fill color.
    """

    for y_value in range(max(0, y_position), min(HEIGHT, y_position + height)):
        for x_value in range(max(0, x_position), min(WIDTH, x_position + width)):
            pixels[y_value][x_value] = color


def draw_rect_outline(
    pixels: list[list[Color]],
    x_position: int,
    y_position: int,
    width: int,
    height: int,
    color: Color,
) -> None:
    """Draw a rectangle outline.

    Args:
        pixels: Pixel matrix to modify.
        x_position: Horizontal position.
        y_position: Vertical position.
        width: Rectangle width.
        height: Rectangle height.
        color: Outline color.
    """

    draw_rect(pixels, x_position, y_position, width, 1, color)
    draw_rect(pixels, x_position, y_position + height - 1, width, 1, color)
    draw_rect(pixels, x_position, y_position, 1, height, color)
    draw_rect(pixels, x_position + width - 1, y_position, 1, height, color)


def write_ppm(path: Path, pixels: list[list[Color]]) -> None:
    """Write a PPM image frame.

    Args:
        path: Output path.
        pixels: Pixel matrix.
    """

    with path.open("wb") as frame_file:
        frame_file.write(f"P6\n{WIDTH} {HEIGHT}\n255\n".encode("ascii"))
        for row in pixels:
            for red, green, blue in row:
                frame_file.write(bytes((red, green, blue)))


if __name__ == "__main__":
    raise SystemExit(main())
