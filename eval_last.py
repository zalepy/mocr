#!/usr/bin/env python3
"""
Evaluate the last captured image using OCR.
Uses 'last_capture.png' from the current directory.
"""

import os
from pathlib import Path
from mocr.ocr import OCREngine

def main():
    capture_path = Path.cwd() / "last_capture.png"
    
    if not capture_path.exists():
        print(f"Error: Last capture file not found at {capture_path}")
        print("Please run screen_ocr.py and perform a capture first.")
        return

    print(f"Processing: {capture_path}")
    
    # Initialize OCR Engine
    engine = OCREngine()
    
    # Process the file
    text = engine.process_file(str(capture_path))
    
    print("=" * 40)
    print("OCR Result:")
    print("=" * 40)
    print(text)
    print("=" * 40)

if __name__ == "__main__":
    main()
