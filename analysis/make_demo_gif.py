"""Turn demo frames (PNG) into a time-lapse GIF, a contact sheet and key frames.

Offline helper for the demo runbook. Pillow only (ffmpeg is not required).

Usage::

    python analysis/make_demo_gif.py FRAMES_DIR OUT_DIR [--every N] [--width W]
    python analysis/make_demo_gif.py FRAMES_DIR OUT_DIR --key 20,60,110,150

``--key`` writes the listed frame indices as JPEGs (``key_<index>.jpg``) instead of
building the GIF.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def frame_paths(directory: Path) -> list[Path]:
    """List the numbered frames in order.

    Args:
        directory: Folder of ``frame_0000.png`` style files.

    Returns:
        The frame paths, sorted by number.
    """
    return sorted(directory.glob("frame_*.png"))


def resized(path: Path, width: int) -> Image.Image:
    """Load a frame and scale it to a width, keeping the aspect ratio.

    Args:
        path: Image file.
        width: Target width in pixels.

    Returns:
        The RGB image.
    """
    img = Image.open(path).convert("RGB")
    height = round(img.height * width / img.width)
    return img.resize((width, height), Image.LANCZOS)


def build_gif(frames: list[Path], out: Path, every: int, width: int, fps: float) -> None:
    """Write a looping GIF from every Nth frame.

    Args:
        frames: Frame paths in order.
        out: Output GIF path.
        every: Keep one frame in this many.
        width: GIF width in pixels.
        fps: Playback speed in frames per second.
    """
    chosen = frames[::every]
    images = [resized(p, width).quantize(colors=64, method=Image.Quantize.MEDIANCUT) for p in chosen]
    images[0].save(
        out,
        save_all=True,
        append_images=images[1:],
        duration=round(1000 / fps),
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"wrote {out} ({len(images)} frames, {out.stat().st_size / 1e6:.1f} MB)")


def build_contact_sheet(frames: list[Path], out: Path, step: int, columns: int = 6, thumb: int = 300) -> None:
    """Write a labelled contact sheet so key moments can be picked by index.

    Args:
        frames: Frame paths in order.
        out: Output image path.
        step: Take every Nth frame.
        columns: Thumbnails per row.
        thumb: Thumbnail width in pixels.
    """
    chosen = list(enumerate(frames))[::step]
    thumbs = [(i, resized(p, thumb)) for i, p in chosen]
    rows = (len(thumbs) + columns - 1) // columns
    th = thumbs[0][1].height
    sheet = Image.new("RGB", (columns * thumb, rows * th), "white")
    draw = ImageDraw.Draw(sheet)
    for k, (i, img) in enumerate(thumbs):
        x, y = (k % columns) * thumb, (k // columns) * th
        sheet.paste(img, (x, y))
        draw.rectangle([x, y, x + 54, y + 16], fill="black")
        draw.text((x + 3, y + 2), f"#{i}", fill="white")
    sheet.save(out)
    print(f"wrote {out} ({len(thumbs)} thumbnails)")


def main() -> None:
    """Parse the command line and write the requested outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames_dir", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--every", type=int, default=2, help="keep one frame in N for the GIF")
    parser.add_argument("--width", type=int, default=640, help="GIF width in pixels")
    parser.add_argument("--fps", type=float, default=8.0)
    parser.add_argument("--key", type=str, default="", help="comma-separated frame indices to export as JPEG")
    parser.add_argument("--sheet-step", type=int, default=8, help="contact sheet: every Nth frame")
    args = parser.parse_args()

    frames = frame_paths(args.frames_dir)
    if not frames:
        raise SystemExit(f"no frames in {args.frames_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"{len(frames)} frames found")

    if args.key:
        for index in (int(s) for s in args.key.split(",")):
            target = args.out_dir / f"key_{index:04d}.jpg"
            resized(frames[min(index, len(frames) - 1)], 1600).save(target, quality=86, optimize=True)
            print(f"wrote {target}")
        return

    build_contact_sheet(frames, args.out_dir / "contact_sheet.png", args.sheet_step)
    build_gif(frames, args.out_dir / "session_timelapse.gif", args.every, args.width, args.fps)


if __name__ == "__main__":
    main()
