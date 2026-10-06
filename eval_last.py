"""
Compare OCR preprocessing strategies on a capture, by eye.

For each strategy this saves the exact image Tesseract sees to the output
folder and prints the recognized text plus Tesseract's mean word confidence
(a hint, not ground truth). Strategies are isolated: each one's image goes to
Tesseract as-is, without the app's default grayscale + sharpen on top.

Usage:
    python eval_last.py                       # evaluates last_capture.png
    python eval_last.py some.png --out eval_out --lang eng
    python eval_last.py --only raw,default,downscale_50
    python eval_last.py --list
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PIL import Image, ImageOps

from mocr.ocr import OCREngine


@dataclass(frozen=True)
class Strategy:
    name: str
    label: str
    transform: Callable[[Image.Image], Image.Image]
    tesseract_config: str = ""


# --- transforms (PIL image in, PIL image out) ---

def raw(img):
    """No preprocessing at all: baseline"""
    return img.convert("RGB")


_app_preprocess = OCREngine.preprocess


def default(img):
    """What the app does today: grayscale + sharpen"""
    return _app_preprocess(img)


def _gray_array(img):
    return np.array(ImageOps.grayscale(img))


def otsu_threshold(img):
    _, thresh = cv2.threshold(_gray_array(img), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh)


def edge_detection(img):
    # Black lines on white background often works better for OCR
    edges = cv2.Canny(_gray_array(img), 50, 150)
    return Image.fromarray(cv2.bitwise_not(edges))


def invert(img):
    """Helpful if text is light on dark background"""
    return ImageOps.invert(img.convert("RGB"))


def scale(factor):
    def _scale(img):
        gray = ImageOps.grayscale(img)
        size = (max(1, round(gray.width * factor)), max(1, round(gray.height * factor)))
        return gray.resize(size, Image.LANCZOS)
    return _scale


def thin_strokes(img):
    """Binarize, make text dark on light, then grow the background to thin bold strokes"""
    binary = np.array(otsu_threshold(img))
    if binary.mean() < 127:  # mostly dark -> light text on dark background
        binary = cv2.bitwise_not(binary)
    kernel = np.ones((3, 3), np.uint8)
    return Image.fromarray(cv2.dilate(binary, kernel, iterations=1))


def pad(img, border=20):
    """Add a border in the image's own edge color; Tesseract dislikes text touching the edge"""
    gray = ImageOps.grayscale(img)
    a = np.array(gray)
    edge = np.concatenate([a[0, :], a[-1, :], a[:, 0], a[:, -1]])
    return ImageOps.expand(gray, border=border, fill=int(np.median(edge)))


STRATEGIES = [
    Strategy("raw", "Raw (no preprocessing)", raw),
    Strategy("default", "Default (app: grayscale + sharpen)", default),
    Strategy("otsu", "Grayscale + Otsu threshold", otsu_threshold),
    Strategy("edges", "Canny edge detection", edge_detection),
    Strategy("invert", "Color inversion", invert),
    Strategy("downscale_50", "Downscale 0.5x (large/bold text)", scale(0.5)),
    Strategy("downscale_33", "Downscale 0.33x (large/bold text)", scale(1 / 3)),
    Strategy("upscale_2x", "Upscale 2x (small text)", scale(2)),
    Strategy("upscale_3x", "Upscale 3x (small text)", scale(3)),
    Strategy("thin_strokes", "Otsu + thin strokes (bold text)", thin_strokes),
    Strategy("pad", "Grayscale + 20px border", pad),
    Strategy("psm6", "Default + --psm 6 (uniform block)", default, "--psm 6"),
    Strategy("psm7", "Default + --psm 7 (single line)", default, "--psm 7"),
    Strategy("psm11", "Default + --psm 11 (sparse text)", default, "--psm 11"),
]


def is_failure(text):
    return text.startswith("ERROR") or text.startswith("(No text detected")


def evaluate(engine, image, strategies, out_dir, language=None):
    """Run each strategy; save its image; return [(strategy, text, confidence, image_path)]"""
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for idx, strategy in enumerate(strategies, start=1):
        try:
            processed = strategy.transform(image)
        except Exception as e:
            results.append((strategy, f"ERROR: transform failed: {e}", -1.0, None))
            continue
        image_path = out_dir / f"{idx:02d}_{strategy.name}.png"
        processed.save(image_path)
        text = engine.recognize(processed, language, strategy.tesseract_config)
        confidence = engine.mean_confidence(processed, language, strategy.tesseract_config)
        results.append((strategy, text, confidence, image_path))
    return results


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Compare OCR preprocessing strategies on a capture.")
    parser.add_argument("image", nargs="?", default="last_capture.png",
                        help="image to evaluate (default: last_capture.png in the current folder)")
    parser.add_argument("--out", default="eval_out", help="folder for the preprocessed images (default: eval_out)")
    parser.add_argument("--lang", default=None, help="Tesseract language (default: Config.LANGUAGE)")
    parser.add_argument("--only", default=None, help="comma-separated strategy names to run")
    parser.add_argument("--list", action="store_true", help="list strategies and exit")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.list:
        for s in STRATEGIES:
            print(f"{s.name:14} {s.label}")
        return 0

    strategies = STRATEGIES
    if args.only:
        wanted = [n.strip() for n in args.only.split(",") if n.strip()]
        unknown = set(wanted) - {s.name for s in STRATEGIES}
        if unknown:
            print(f"Unknown strategies: {', '.join(sorted(unknown))}. Use --list.")
            return 2
        strategies = [s for s in STRATEGIES if s.name in wanted]

    capture_path = Path(args.image)
    if not capture_path.exists():
        print(f"Error: image not found at {capture_path.resolve()}")
        print("Run screen_ocr.py and perform a capture first, or pass an image path.")
        return 1

    print(f"Processing: {capture_path}")
    image = Image.open(capture_path)
    image.load()
    print(f"Size: {image.width}x{image.height}, mode {image.mode}")
    out_dir = Path(args.out)
    print(f"Preprocessed images: {out_dir.resolve()}\n")

    engine = OCREngine()
    results = evaluate(engine, image, strategies, out_dir, args.lang)

    for strategy, text, confidence, image_path in results:
        print("=" * 60)
        print(f"Strategy: {strategy.label} [{strategy.name}]")
        conf_text = f"{confidence:.0f}" if confidence >= 0 else "n/a"
        print(f"Confidence: {conf_text}   Image: {image_path.name if image_path else '-'}")
        print("-" * 60)
        if is_failure(text):
            print(f"RESULT: (FAILED/EMPTY) -> {text}")
        else:
            print("RESULT:")
            print(text)
        print("=" * 60 + "\n")

    print("Summary")
    print(f"{'strategy':14} {'conf':>5} {'chars':>6}  first line")
    for strategy, text, confidence, _ in results:
        conf_text = f"{confidence:.0f}" if confidence >= 0 else "-"
        chars = "-" if is_failure(text) else str(len(text))
        first = "" if is_failure(text) else text.splitlines()[0][:40]
        print(f"{strategy.name:14} {conf_text:>5} {chars:>6}  {first}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
