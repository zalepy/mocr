"""
OCR preprocessing strategies: small, pure `PIL.Image -> PIL.Image` transforms.

The app uses these for the default OCR pass and the tray's "Re-OCR last capture
with" menu; eval_last.py compares them side by side. Pillow only, no OpenCV.
"""

import statistics
from dataclasses import dataclass
from typing import Callable, Optional

from PIL import Image, ImageFilter, ImageOps


@dataclass(frozen=True)
class Strategy:
    name: str
    label: str
    transform: Callable[[Image.Image], Image.Image]
    tesseract_config: str = ""


# Tesseract reads best when a text line is roughly 15-35 px tall: much smaller
# and characters merge, much larger (e.g. big headings, or 2x device pixels on a
# 200% display) and it often detects nothing. auto_scale aims for the middle.
TARGET_LINE_HEIGHT = 22
MIN_SCALE, MAX_SCALE = 0.2, 4.0
SCALE_DEADBAND = (0.8, 1.25)  # close enough: don't resample


# --- helpers ---

def otsu_level(gray: Image.Image) -> int:
    """Otsu's threshold for an 'L' image: the level that best splits it into two classes"""
    hist = gray.histogram()
    total = sum(hist)
    sum_all = sum(i * h for i, h in enumerate(hist))
    weight_bg = sum_bg = 0
    best_var, best_level = -1.0, 127
    for level in range(256):
        weight_bg += hist[level]
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break
        sum_bg += level * hist[level]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_all - sum_bg) / weight_fg
        var = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if var > best_var:
            best_var, best_level = var, level
    return best_level


def binarize_dark_on_light(img: Image.Image) -> Image.Image:
    """Otsu-binarize to black text on a white background (inverting light-on-dark text)"""
    gray = ImageOps.grayscale(img)
    level = otsu_level(gray)
    binary = gray.point(lambda p: 255 if p > level else 0)
    white = binary.histogram()[255]
    if white < binary.width * binary.height / 2:  # mostly dark -> light text on dark
        binary = ImageOps.invert(binary)
    return binary


def estimate_line_height(img: Image.Image) -> Optional[float]:
    """
    Median height in px of the text lines, from the horizontal ink profile:
    rows containing ink, grouped into runs. None if no text-like rows are found.
    """
    ink = ImageOps.invert(binarize_dark_on_light(img))  # ink = white
    # Squeezing to 1 px wide averages each row: per-row ink fraction * 255
    profile = ink.resize((1, ink.height), Image.BOX).tobytes()
    runs, run = [], 0
    for value in profile + b"\0":
        if value > 255 * 0.01:
            run += 1
        elif run:
            runs.append(run)
            run = 0
    runs = [r for r in runs if r >= 3]  # ignore rules / specks
    return float(statistics.median(runs)) if runs else None


def _resize(img: Image.Image, factor: float) -> Image.Image:
    size = (max(1, round(img.width * factor)), max(1, round(img.height * factor)))
    return img.resize(size, Image.LANCZOS)


# --- transforms ---

def raw(img):
    """No preprocessing at all: baseline"""
    return img.convert("RGB")


def default(img):
    """The app's original default: grayscale + sharpen"""
    return ImageOps.grayscale(img).filter(ImageFilter.SHARPEN)


def auto_scale_factor(img: Image.Image) -> float:
    """Scale factor that brings the text toward TARGET_LINE_HEIGHT (1.0 = leave as is)"""
    height = estimate_line_height(img)
    if not height:
        return 1.0
    factor = min(MAX_SCALE, max(MIN_SCALE, TARGET_LINE_HEIGHT / height))
    low, high = SCALE_DEADBAND
    return 1.0 if low <= factor <= high else factor


def auto_scale(img):
    """
    Grayscale, up- or downscale so text lines are ~TARGET_LINE_HEIGHT px, and
    sharpen unless upscaled (sharpening amplifies upscaling artifacts).
    """
    gray = ImageOps.grayscale(img)
    factor = auto_scale_factor(gray)
    if factor > 1.0:
        return _resize(gray, factor)
    scaled = gray if factor == 1.0 else _resize(gray, factor)
    return scaled.filter(ImageFilter.SHARPEN)


def scale(factor):
    def _scale(img):
        return _resize(ImageOps.grayscale(img), factor)
    return _scale


def invert(img):
    """Helpful if text is light on dark background"""
    return ImageOps.invert(img.convert("RGB"))


def otsu_threshold(img):
    gray = ImageOps.grayscale(img)
    level = otsu_level(gray)
    return gray.point(lambda p: 255 if p > level else 0)


def thin_strokes(img):
    """Binarize to dark-on-light, then grow the background to thin bold strokes"""
    return binarize_dark_on_light(img).filter(ImageFilter.MaxFilter(3))


def pad(img, border=20):
    """Add a border in the image's own edge color; Tesseract dislikes text touching the edge"""
    gray = ImageOps.grayscale(img)
    w, h = gray.size
    edges = [gray.crop(box).tobytes() for box in
             ((0, 0, w, 1), (0, h - 1, w, h), (0, 0, 1, h), (w - 1, 0, w, h))]
    fill = int(statistics.median(b"".join(edges)))
    return ImageOps.expand(gray, border=border, fill=fill)


STRATEGIES = [
    Strategy("auto_scale", "Auto scale (fit text size + sharpen)", auto_scale),
    Strategy("default", "Default (grayscale + sharpen)", default),
    Strategy("raw", "Raw (no preprocessing)", raw),
    Strategy("downscale_50", "Downscale 0.5x (large/bold text)", scale(0.5)),
    Strategy("downscale_33", "Downscale 0.33x (large/bold text)", scale(1 / 3)),
    Strategy("upscale_2x", "Upscale 2x (small text)", scale(2)),
    Strategy("upscale_3x", "Upscale 3x (small text)", scale(3)),
    Strategy("invert", "Invert colors", invert),
    Strategy("otsu", "Grayscale + Otsu threshold", otsu_threshold),
    Strategy("thin_strokes", "Otsu + thin strokes (bold text)", thin_strokes),
    Strategy("pad", "Grayscale + 20px border", pad),
    Strategy("psm6", "Default + --psm 6 (uniform block)", default, "--psm 6"),
    Strategy("psm7", "Default + --psm 7 (single line)", default, "--psm 7"),
    Strategy("psm11", "Default + --psm 11 (sparse text)", default, "--psm 11"),
]

STRATEGIES_BY_NAME = {s.name: s for s in STRATEGIES}
