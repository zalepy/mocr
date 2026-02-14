"""
Pytest configuration and fixtures

This module provides shared fixtures and configuration for all tests.
"""

import pytest
import sys
from pathlib import Path

# Ensure the parent directory is in the path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def sample_image_path():
    """Provide path to sample OCR test image"""
    path = Path(__file__).parent / "sample.png"
    if not path.exists():
        pytest.skip(f"Sample image not found at {path}")
    return path


@pytest.fixture(scope="session")
def project_root():
    """Provide project root directory"""
    return Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def reset_clipboard_between_tests():
    """Reset clipboard state between tests to avoid interference"""
    yield
    # Cleanup after each test - clear the test data from clipboard
    from screen_ocr import ClipboardManager
    try:
        ClipboardManager.copy_text("")
    except Exception:
        pass


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "ocr: marks tests that require OCR engine"
    )
    config.addinivalue_line(
        "markers", "clipboard: marks clipboard-related tests"
    )
    config.addinivalue_line(
        "markers", "windows: marks Windows-specific tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names"""
    for item in items:
        # Mark OCR-related tests (only tests that specifically process images)
        if "process_image" in item.nodeid.lower():
            item.add_marker(pytest.mark.ocr)
            item.add_marker(pytest.mark.slow)
        
        # Mark clipboard tests
        if "clipboard" in item.nodeid.lower():
            item.add_marker(pytest.mark.clipboard)
        
        # Mark windows tests
        if "windows" in item.nodeid.lower() or "registry" in item.nodeid.lower() or "startup" in item.nodeid.lower():
            item.add_marker(pytest.mark.windows)
        
        # Mark slow tests (sample image tests)
        if "sample" in item.nodeid.lower():
            item.add_marker(pytest.mark.slow)
