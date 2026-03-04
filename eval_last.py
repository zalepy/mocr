import os
import cv2
import numpy as np
from pathlib import Path
from PIL import Image
from mocr.ocr import OCREngine

def process_with_strategy(engine, image_path, strategy_name):
    """Process image using a specific strategy and return extracted text."""
    try:
        # Load the image
        img = cv2.imread(str(image_path))
        if img is None:
            return f"Error: Could not read image at {image_path}"

        if strategy_name == "default":
            return engine.process_file(str(image_path))

        elif strategy_name == "grayscale_threshold":
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Apply Otsu's thresholding
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # Convert back to PIL for engine
            pil_img = Image.fromarray(thresh)
            return engine.process_pil_image(pil_img)

        elif strategy_name == "edge_detection":
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Apply Canny edge detection
            edges = cv2.Canny(gray, 50, 150)
            # Invert edges: black lines on white background often works better for OCR
            edges_inv = cv2.bitwise_not(edges)
            # Convert back to PIL for engine
            pil_img = Image.fromarray(edges_inv)
            return engine.process_pil_image(pil_img)

        elif strategy_name == "invert":
            # Invert colors (helpful if text is light on dark background)
            inverted = cv2.bitwise_not(img)
            pil_img = Image.fromarray(cv2.cvtColor(inverted, cv2.COLOR_BGR2RGB))
            return engine.process_pil_image(pil_img)

        else:
            return f"Unknown strategy: {strategy_name}"

    except Exception as e:
        return f"Strategy {strategy_name} failed: {str(e)}"

def main():
    capture_path = Path.cwd() / "last_capture.png"
    
    if not capture_path.exists():
        print(f"Error: Last capture file not found at {capture_path}")
        print("Please run screen_ocr.py and perform a capture first.")
        return

    print(f"Processing: {capture_path}\n")
    
    # Initialize OCR Engine
    engine = OCREngine()
    
    strategies = [
        ("Default (Standard OCR)", "default"),
        ("Grayscale + Thresholding", "grayscale_threshold"),
        ("Canny Edge Detection", "edge_detection"),
        ("Color Inversion", "invert")
    ]
    
    for label, strategy_id in strategies:
        print("=" * 60)
        print(f"Strategy: {label}")
        print("-" * 60)
        
        text = process_with_strategy(engine, capture_path, strategy_id)
        
        # Check if it "failed" (return default message if no text detected)
        if "(No text detected" in text or "ERROR" in text:
            print(f"RESULT: (FAILED/EMPTY) -> {text}")
        else:
            print("RESULT:")
            print(text)
        print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
