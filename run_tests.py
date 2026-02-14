"""
Test utilities and helper functions for running test suite with coverage

This module provides utilities for running tests with coverage reporting.
"""

import subprocess
import sys
from pathlib import Path


def run_tests(args=None):
    """
    Run tests with pytest and coverage reporting
    
    Args:
        args: Additional arguments to pass to pytest
    """
    if args is None:
        args = []
    
    # Base pytest command with coverage
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "--cov=screen_ocr",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-report=xml",
    ] + args
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    return result.returncode


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Screen OCR tests with coverage")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip slow tests (like OCR processing)"
    )
    parser.add_argument(
        "--only-ocr",
        action="store_true",
        help="Run only OCR-related tests"
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Run tests without coverage reporting"
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Additional arguments to pass to pytest"
    )
    
    args = parser.parse_args()
    
    cmd_args = []
    
    if args.no_coverage:
        cmd_args.append("--no-cov")
    
    if args.fast:
        cmd_args.append('-m')
        cmd_args.append('not slow')
    
    if args.only_ocr:
        cmd_args.append('-m')
        cmd_args.append('ocr')
    
    cmd_args.extend(args.pytest_args)
    
    sys.exit(run_tests(cmd_args))
