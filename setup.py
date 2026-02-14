#!/usr/bin/env python3
"""
Setup script for Screen OCR Tool
Run this to check dependencies and configure the application.
"""

import sys
import os
import subprocess
from pathlib import Path

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ is required!")
        return False
    
    print("✓ Python version OK")
    return True

def check_tesseract():
    """Check if Tesseract OCR is installed"""
    print("\nChecking Tesseract OCR...")
    
    # Try to find tesseract in PATH
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            version = result.stderr.split('\n')[0] if result.stderr else "Unknown"
            print(f"✓ Tesseract found: {version}")
            return True
    except FileNotFoundError:
        pass
    
    # Check common Windows paths
    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Tesseract-OCR\tesseract.exe",
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            print(f"✓ Tesseract found at: {path}")
            print("  Note: You may need to add this to your PATH or update Config.TESSERACT_PATH")
            return True
    
    print("❌ Tesseract OCR not found!")
    print("\nPlease install Tesseract OCR:")
    print("  Windows: https://github.com/UB-Mannheim/tesseract/wiki")
    print("  Linux:   sudo apt install tesseract-ocr")
    print("  macOS:   brew install tesseract")
    return False

def check_python_packages():
    """Check if required Python packages are installed"""
    print("\nChecking Python packages...")
    
    packages = {
        "PyQt5": "PyQt5",
        "pytesseract": "pytesseract",
        "Pillow": "Pillow",
        "keyboard": "keyboard",
    }
    
    all_installed = True
    for name, import_name in packages.items():
        try:
            __import__(import_name)
            print(f"✓ {name} installed")
        except ImportError:
            print(f"❌ {name} not installed")
            all_installed = False
    
    if not all_installed:
        print("\nTo install missing packages, run:")
        print("  pip install -r requirements.txt")
    
    return all_installed

def check_win32():
    """Check if pywin32 is available (Windows only)"""
    if sys.platform != 'win32':
        return True
    
    print("\nChecking Windows integration...")
    try:
        import win32api
        import win32clipboard
        print("✓ pywin32 installed (enhanced clipboard support)")
        return True
    except ImportError:
        print("⚠ pywin32 not installed (optional, for enhanced Windows support)")
        print("  Install with: pip install pywin32")
        return True  # Optional, not required

def create_desktop_shortcut():
    """Create a desktop shortcut (Windows only)"""
    if sys.platform != 'win32':
        print("\nDesktop shortcut creation is only available on Windows.")
        return
    
    print("\nWould you like to create a desktop shortcut? (y/n): ", end="")
    choice = input().strip().lower()
    
    if choice != 'y':
        return
    
    try:
        import win32com.client
        
        desktop = Path.home() / "Desktop"
        script_path = Path(__file__).parent / "screen_ocr.py"
        
        # Create shortcut
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(desktop / "Screen OCR.lnk"))
        shortcut.TargetPath = sys.executable
        shortcut.Arguments = f'"{script_path}"'
        shortcut.WorkingDirectory = str(script_path.parent)
        shortcut.IconLocation = sys.executable  # Use Python icon
        shortcut.save()
        
        print("✓ Desktop shortcut created!")
    except Exception as e:
        print(f"❌ Failed to create shortcut: {e}")
        print("  You can manually create a shortcut to: python screen_ocr.py")

def main():
    """Run setup checks"""
    print("=" * 50)
    print("Screen OCR Tool - Setup")
    print("=" * 50)
    
    # Run checks
    checks = [
        ("Python version", check_python_version),
        ("Tesseract OCR", check_tesseract),
        ("Python packages", check_python_packages),
        ("Windows integration", check_win32),
    ]
    
    results = {}
    for name, check_func in checks:
        results[name] = check_func()
    
    print("\n" + "=" * 50)
    print("Setup Summary")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results.items():
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✓ All checks passed! You're ready to use Screen OCR Tool.")
        print("\nTo start the application, run:")
        print("  python screen_ocr.py")
        
        # Offer to create shortcut
        create_desktop_shortcut()
    else:
        print("\n❌ Some checks failed. Please fix the issues above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
