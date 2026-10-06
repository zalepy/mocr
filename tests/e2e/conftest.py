"""
End-to-end test fixtures.

These tests interact with the real OS: they show the tray icon and its
notifications, write the clipboard, and run Tesseract. Run them explicitly:

    pytest tests/e2e
"""

import pytest
from pathlib import Path

SAMPLES_DIR = Path(__file__).parent


@pytest.fixture(scope="session")
def sample_image_path():
    """Provide path to sample OCR test image"""
    path = SAMPLES_DIR / "sample.png"
    if not path.exists():
        pytest.skip(f"Sample image not found at {path}")
    return path


@pytest.fixture(scope="session")
def sample2_image_path():
    """Provide path to second sample OCR test image"""
    path = SAMPLES_DIR / "sample2.png"
    if not path.exists():
        pytest.skip(f"Sample2 image not found at {path}")
    return path


@pytest.fixture(scope="session")
def sample3_image_path():
    """Provide path to third sample (white text on blue band + photo) OCR test image"""
    path = SAMPLES_DIR / "sample3.png"
    if not path.exists():
        pytest.skip(f"Sample3 image not found at {path}")
    return path


@pytest.fixture
def preserve_clipboard(qapp):
    """Restore the user's clipboard text after a test that writes to it"""
    from mocr.clipboard import ClipboardManager
    saved = ClipboardManager.get_text()
    yield
    # Restore through ClipboardManager (Qt + win32), same path the app uses
    ClipboardManager.copy_text(saved)
