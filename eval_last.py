"""
Compare OCR preprocessing strategies on a capture, by eye.

For each strategy this saves the exact image Tesseract sees to the output
folder and prints the recognized text plus Tesseract's mean word confidence
(a hint, not ground truth). Strategies are isolated: each one's image goes to
Tesseract as-is, without the app's default grayscale + sharpen on top.

Usage:
    python eval_last.py                       # evaluates last_capture.png
    python eval_last.py some.png --out eval_out --lang eng
    python eval_last.py --only raw,default,auto_scale
    python eval_last.py --list
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

from mocr.ocr import OCREngine
from mocr.preprocess import STRATEGIES as APP_STRATEGIES, Strategy


def edge_detection(img):
    """Canny edges as black lines on white. Eval-only: needs OpenCV (eval group)"""
    import cv2
    import numpy as np
    from PIL import ImageOps
    edges = cv2.Canny(np.array(ImageOps.grayscale(img)), 50, 150)
    return Image.fromarray(cv2.bitwise_not(edges))


# The app's strategies (mocr.preprocess) plus experiments not shipped in the app
STRATEGIES = APP_STRATEGIES + [
    Strategy("edges", "Canny edge detection (eval only)", edge_detection),
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
