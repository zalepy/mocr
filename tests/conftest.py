"""
Pytest configuration and fixtures shared by unit and e2e tests.

Layout:
- tests/unit: isolated tests that never touch the OS (tray, notifications,
  clipboard, screens, Tesseract). Run by default with `pytest`.
- tests/e2e: tests that exercise the real OS integration. Run explicitly with
  `pytest tests/e2e`.
"""

import pytest
import sys
from pathlib import Path


E2E_DIR = Path(__file__).parent / "e2e"


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for all tests"""
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture(scope="session")
def project_root():
    """Provide project root directory"""
    return Path(__file__).parent.parent


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "e2e: tests that interact with the real OS (tray, clipboard, screens, Tesseract)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "ocr: marks tests that require OCR engine"
    )
    config.addinivalue_line(
        "markers", "clipboard: marks clipboard-related tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on location and test names"""
    for item in items:
        if E2E_DIR in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.e2e)

        # Mark OCR-related tests (only tests that specifically process images)
        if "process_image" in item.nodeid.lower():
            item.add_marker(pytest.mark.ocr)
            item.add_marker(pytest.mark.slow)

        # Mark clipboard tests
        if "clipboard" in item.nodeid.lower():
            item.add_marker(pytest.mark.clipboard)

        # Mark slow tests (sample image tests)
        if "sample" in item.nodeid.lower():
            item.add_marker(pytest.mark.slow)
