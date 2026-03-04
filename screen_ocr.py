#!/usr/bin/env python3
"""
Screen Capture OCR Tool
A Windows-like screen capture tool that performs OCR on the selected region
and copies the text to clipboard instead of the image.

Usage:
    python screen_ocr.py [--debug]
"""

from mocr.app import main

if __name__ == "__main__":
    main()
